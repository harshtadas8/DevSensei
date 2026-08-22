from fastapi import FastAPI, BackgroundTasks
import structlog
from pydantic import BaseModel
from .agents.graph import devsensei_graph
from langchain_core.messages import HumanMessage

logger = structlog.get_logger()
app = FastAPI(title="DevSensei Agent Orchestrator")

class AnalysisRequest(BaseModel):
    repo_path: str
    pr_number: int | None = None
    custom_rules: str = ""

@app.get("/health")
def health_check():
    logger.info("health_check_called", status="ok")
    return {"status": "ok"}

from fastapi.responses import StreamingResponse
import asyncio
import json

from .ingestion.indexer import index_repository, retrieve_context

@app.post("/analyze")
async def analyze_code(request: AnalysisRequest):
    """
    Triggers the multi-agent LangGraph workflow via SSE stream for real-time frontend updates.
    """
    logger.info("starting_analysis_stream", repo_path=request.repo_path)
    
    async def event_generator():
        # Step 1: Clone/Ingest
        yield f"data: {json.dumps({'stage': 'ingest', 'log': f'Fetching repository files from {request.repo_path}...'})}\n\n"
        await asyncio.sleep(0.5)
        
        # Step 2: Parse & Embed
        yield f"data: {json.dumps({'stage': 'parse', 'log': 'Extracting AST with tree-sitter and generating embeddings for ChromaDB...'})}\n\n"
        
        try:
            repo_path = request.repo_path
            # If the user pasted a GitHub URL in the frontend, clone it temporarily!
            if repo_path.startswith("http://") or repo_path.startswith("https://"):
                import subprocess
                from urllib.parse import urlparse
                repo_name = urlparse(repo_path).path.strip('/')
                clone_dir = f"/tmp/{repo_name.replace('/', '_')}_manual"
                subprocess.run(["rm", "-rf", clone_dir], capture_output=True)
                subprocess.run(["git", "clone", repo_path, clone_dir], check=True)
                repo_path = clone_dir
            
            num_chunks = await asyncio.to_thread(index_repository, repo_path)
            if num_chunks == 0:
                yield f"data: {json.dumps({'stage': 'complete', 'results': {'status': 'error', 'final_report': 'No supported code files found in this repository to analyze.'}})}\n\n"
                return
            yield f"data: {json.dumps({'stage': 'embed', 'log': f'Successfully indexed {num_chunks} code chunks into ChromaDB.'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'embed', 'log': f'Error during indexing: {e}'})}\n\n"
            
        await asyncio.sleep(0.5)

        # Step 3: Agents
        yield f"data: {json.dumps({'stage': 'agents', 'log': 'Orchestrating multi-agent graph (Architect, Reviewer, Tester)...'})}\n\n"
        
        # Retrieve actual context from ChromaDB
        sample_code = await asyncio.to_thread(retrieve_context, "Application architecture, security, logic, and tests", 4)
        if not sample_code.strip():
            # Fallback if no context is found
            sample_code = "No supported code found in the repository."

        # Initialize the graph state
        initial_state = {
            "messages": [HumanMessage(content=f"Here is the codebase context retrieved from ChromaDB for you to analyze:\n\n```python\n{sample_code}\n```")],
            "repo_path": repo_path,
            "pr_number": request.pr_number,
            "custom_rules": request.custom_rules,
            "current_agent": "system",
            "reviewer_notes": "",
            "architect_notes": "",
            "tester_notes": "",
            "final_report": ""
        }
        
        # Run the graph synchronously inside the async generator (safe for this demo/MVP)
        final_state = devsensei_graph.invoke(initial_state)
        
        # Send final results
        # Build file list for the Code Viewer
        repo_files = []
        for root, dirs, files in os.walk(repo_path):
            # Skip hidden dirs like .git
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.yml', '.yaml', '.md')):
                    # Store relative path
                    rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                    # Use forward slashes for cross-platform compatibility in the UI
                    repo_files.append(rel_path.replace("\\", "/"))

        results_data = {
            'status': 'success',
            'reviewer_notes': final_state.get('reviewer_notes'),
            'architect_notes': final_state.get('architect_notes'),
            'tester_notes': final_state.get('tester_notes'),
            'final_report': final_state.get('final_report'),
            'repo_path': repo_path,
            'files': sorted(repo_files)
        }
        yield f"data: {json.dumps({'stage': 'complete', 'results': results_data})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/file")
async def get_file_content(path: str):
    """
    Phase 6: Code Viewer Endpoint
    Returns the content of a file for the UI to display.
    In a real app, this would use MCP. For this MVP, we read locally.
    """
    try:
        # Very basic path traversal protection for demo
        safe_path = os.path.abspath(path)
        if not os.path.exists(safe_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Phase 5: GitHub Integration & Automation Layer ---

class ChatRequest(BaseModel):
    query: str
    repo_path: str

@app.post("/chat")
async def chat_with_repo(request: ChatRequest):
    """
    Phase 9 (Option B): Interactive Chat Interface
    Answers user questions about the repository using RAG.
    """
    logger.info("chat_query_received", query=request.query)
    
    try:
        from .ingestion.indexer import retrieve_context
        # Retrieve the most relevant 3 chunks from ChromaDB
        context = await asyncio.to_thread(retrieve_context, request.query, 3)
        
        if not context.strip():
            context = "No relevant code found in the repository."

        from .agents.nodes import get_llm
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Initialize the global LLM configured for the project (Groq / Gemini)
        chat_model = get_llm()
        
        system_prompt = (
            "You are an expert AI pair programmer named DevSensei.\n"
            "You are helping a developer understand and modify their code.\n"
            "Below is the relevant code from their repository based on their question.\n"
            "Read it carefully and provide a helpful, concise, and accurate answer.\n"
            "If they ask you to write code, provide the exact code block.\n\n"
            "=== RETRIEVED REPOSITORY CONTEXT ===\n"
            f"{context}\n"
            "===================================\n"
        )
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=request.query)
        ]
        
        response = await chat_model.ainvoke(messages)
        
        return {
            "status": "success",
            "answer": response.content,
            "retrieved_context": context
        }
        
    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

import hmac
import hashlib
import os
from fastapi import Request, HTTPException

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "devsensei_secret")

def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    hash_object = hmac.new(GITHUB_WEBHOOK_SECRET.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

import subprocess
import shutil

async def process_pull_request(pr_number: int, repo_full_name: str, clone_url: str):
    """
    Background task to run LangGraph and post the comment back.
    """
    logger.info("processing_pr_background", pr=pr_number, repo=repo_full_name)
    
    # 1. Clone the repository
    repo_path = f"/tmp/{repo_full_name.replace('/', '_')}_{pr_number}"
    
    # Clean up existing if needed
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
        
    logger.info("cloning_repo", url=clone_url, path=repo_path)
    try:
        # Clone it! (Will only work seamlessly for public repos in this MVP)
        subprocess.run(["git", "clone", "--depth", "1", clone_url, repo_path], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error("git_clone_failed", error=e.stderr.decode())
        return
        
    # Index the newly cloned repo in ChromaDB
    try:
        from .ingestion.indexer import index_repository, retrieve_context
        await asyncio.to_thread(index_repository, repo_path)
        sample_code = await asyncio.to_thread(retrieve_context, "Application architecture, security, logic, and tests", 4)
    except Exception as e:
        logger.error("indexing_failed", error=str(e))
        sample_code = "Error indexing repository."
    
    # 2. Run the graph
    initial_state = {
        "messages": [HumanMessage(content=f"Please analyze PR #{pr_number} for {repo_full_name}. Here is context:\n\n```python\n{sample_code}\n```")],
        "repo_path": repo_path,
        "pr_number": pr_number,
        "custom_rules": "",
        "current_agent": "system",
        "reviewer_notes": "",
        "architect_notes": "",
        "tester_notes": "",
        "final_report": ""
    }
    
    final_state = devsensei_graph.invoke(initial_state)
    
    # 3. Post the result back to the GitHub PR!
    logger.info("pr_analysis_complete", pr=pr_number)
    final_report = final_state.get('final_report', 'No report generated.')
    
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        from github import Github
        try:
            g = Github(github_token)
            repo = g.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(f"## 🤖 DevSensei AI PR Review\n\n{final_report}")
            logger.info("posted_github_comment_success", pr=pr_number)
        except Exception as e:
            logger.error("github_post_failed", error=str(e))
    else:
        print("\n\n=== DEVSENSEI AI PR REVIEW REPORT ===\n")
        print(final_report)
        print("\n=====================================\n")

class FixRequest(BaseModel):
    repo_path: str
    reviewer_notes: str

@app.post("/fix")
async def autofix_code(request: FixRequest):
    """
    Phase 9 (Option C): Automated PR Fixes
    Generates fully fixed code using the Coder Agent based on the Reviewer's findings.
    """
    logger.info("autofix_requested", repo_path=request.repo_path)
    try:
        from .ingestion.indexer import retrieve_context
        from .agents.nodes import coder_node
        from langchain_core.messages import HumanMessage
        
        # We need the codebase context to know what to fix
        context = await asyncio.to_thread(retrieve_context, request.reviewer_notes, 5)
        
        # Calculate local path for editing
        local_repo_path = request.repo_path
        if local_repo_path.startswith("http://") or local_repo_path.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(local_repo_path)
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2:
                local_repo_path = f"/tmp/{parts[0]}_{parts[1].replace('.git', '')}_manual"
        
        # Build a mock state for the coder_node
        state = {
            "messages": [HumanMessage(content=f"Codebase Context:\n\n{context}")],
            "repo_path": local_repo_path,
            "reviewer_notes": request.reviewer_notes,
            "custom_rules": "",
            "pr_number": 0,
            "current_agent": "system",
            "architect_notes": "",
            "tester_notes": "",
            "final_report": ""
        }
        
        # Run the Coder Agent
        result = await asyncio.to_thread(coder_node, state)
        return {"fixed_code": result["final_report"]}
        
    except Exception as e:
        logger.error("fix_error", error=str(e))
        return {"error": str(e)}

if not os.environ.get("GITHUB_TOKEN"):
    logger.warning("GITHUB_TOKEN_not_set_printing_to_console")

@app.post("/api/github/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives events from GitHub Apps, verifies signatures, and enqueues reviews to avoid timeouts.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()
    
    if not verify_github_signature(body, signature):
        logger.warning("invalid_github_signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    event_type = request.headers.get("X-GitHub-Event")
    payload = await request.json()
    
    # Handle PR opened/synchronize
    if event_type == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize"]:
            pr_number = payload["pull_request"]["number"]
            repo_full_name = payload["repository"]["full_name"]
            clone_url = payload["repository"]["clone_url"]
            
            logger.info("pr_event_received", action=action, pr=pr_number)
            
            # Enqueue the background task so we return 200 OK to GitHub immediately
            background_tasks.add_task(process_pull_request, pr_number, repo_full_name, clone_url)
            
            return {"status": "accepted", "message": f"PR #{pr_number} queued for analysis"}
            
    return {"status": "ignored", "message": "Event not handled by DevSensei"}


