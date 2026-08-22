from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from .state import AgentState
import os

from langchain_core.globals import set_llm_cache
from langchain_core.caches import InMemoryCache

# Enable in-memory caching to save API tokens and speed up redundant requests
set_llm_cache(InMemoryCache())

# Helper to get the LLM (Supports Groq for free tier, Gemini as fallback)
def get_llm():
    if os.environ.get("GROQ_API_KEY"):
        # Switched to Llama 3.1 70B to bypass rate limits on the other model
        return ChatGroq(temperature=0, model_name="llama-3.1-70b-versatile", max_retries=10, request_timeout=60) 
    elif os.environ.get("GOOGLE_API_KEY"):
        return ChatGoogleGenerativeAI(model="gemini-2.5-pro")
        
    # Dummy LLM fallback for safe local testing without API keys
    class DummyLLM:
        def invoke(self, messages):
            text = str(messages[0].content)
            if "Architecture" in text or "Mermaid" in text:
                return HumanMessage(content="""```mermaid
graph TD
    A[Next.js Frontend] -->|REST| B(FastAPI Orchestrator)
    B --> C{LangGraph Agents}
    C -->|Read| D[MCP Server]
    D --> E[(Local File System)]
    C -->|Embeddings| F[(ChromaDB)]
```
[LLM Mock] Architectural diagram generated. Add an API key for real diagrams!""")
            return HumanMessage(content="[LLM Mock] Analysis complete. Add an API key to your .env to see real insights!")
    return DummyLLM()

def code_reviewer_node(state: AgentState):
    llm = get_llm()
    messages = state.get('messages', [])
    custom_rules = state.get('custom_rules', "")
    rules_prompt = f"\n\nCRITICAL TEAM RULES TO ENFORCE:\n{custom_rules}\n(You must enforce these team rules during your code review if applicable.)\n" if custom_rules else ""

    prompt = SystemMessage(content=(
        "You are the DevSensei Code Reviewer. "
        "Analyze the provided codebase for logic bugs, security vulnerabilities, and performance bottlenecks. "
        "Provide a concise, bulleted markdown report. Limit your report to the TOP 5 most critical issues to save tokens. "
        "CRITICAL: You MUST provide an analysis. Do NOT output an empty string. "
        "Start your response EXACTLY with '# Security & Logic Review\n\n' and list your findings. "
        "CRITICAL: If you output any tables, you MUST use standard Markdown syntax with a mandatory separator row (e.g., | Col1 | Col2 |\n|---|---|)."
        f"{rules_prompt}"
    ))
    response = llm.invoke([prompt] + list(messages))
    import time; time.sleep(10)
    return {"reviewer_notes": response.content, "current_agent": "reviewer"}

def architecture_node(state: AgentState):
    llm = get_llm()
    messages = state.get('messages', [])
    prompt = SystemMessage(content=(
        "You are the DevSensei Architecture Agent. "
        "Review the codebase and generate a Mermaid.js flowchart (graph TD) visualizing the high-level architecture. "
        "You MUST wrap the Mermaid syntax exactly in ```mermaid ... ``` code blocks. "
        "CRITICAL MERMAID RULES: \n"
        "1. Do NOT use parentheses (), square brackets [], or slashes / inside node text or node IDs unless strictly quoted.\n"
        "2. Keep node text simple and alphanumeric (e.g. `A[FastAPI App]` is good, `A[FastAPI (Server)]` is BAD). \n"
        "3. Provide ONLY the mermaid code block. Do not output any conversational text or explanation."
    ))
    response = llm.invoke([prompt] + list(messages))
    import time; time.sleep(10)
    return {"architect_notes": response.content, "current_agent": "architect"}

def tester_node(state: AgentState):
    llm = get_llm()
    messages = state.get('messages', [])
    custom_rules = state.get('custom_rules', "")
    rules_prompt = f"\n\nCRITICAL TEAM RULES TO ENFORCE:\n{custom_rules}\n(Ensure any test suggestions comply with these rules.)\n" if custom_rules else ""

    prompt = SystemMessage(content=(
        "You are the DevSensei Test Generator. "
        "Based on the provided codebase, suggest missing unit tests and identify edge cases. "
        "Outline a concise test plan using Markdown tables. Limit to the TOP 5 most important test cases to save tokens. "
        "CRITICAL: Do NOT output empty strings. Always provide a full test plan. "
        "CRITICAL: You MUST separate markdown table rows with actual line breaks (\\n). "
        "CRITICAL: All tables MUST include the mandatory separator row directly beneath the header (e.g. |---|---|)."
        f"{rules_prompt}"
    ))
    response = llm.invoke([prompt] + list(messages))
    import time; time.sleep(10)
    return {"tester_notes": response.content, "current_agent": "tester"}

def synthesizer_node(state: AgentState):
    llm = get_llm()
    reviewer = state.get('reviewer_notes', '')
    architect = state.get('architect_notes', '')
    tester = state.get('tester_notes', '')
    prompt = SystemMessage(content=(
        "You are the DevSensei Synthesizer Agent. "
        "Merge the following reports into a single, cohesive, highly readable GitHub PR comment. "
        "De-duplicate any overlapping points and rank findings by severity. "
        "CRITICAL: Ensure all markdown tables are properly formatted with standard line breaks (\\n) between rows. "
        "CRITICAL: All tables MUST include the mandatory separator row directly beneath the header (e.g. |---|---|). "
        "Do NOT include the raw Mermaid diagram in this text. The UI handles the diagram separately. Just synthesize the text observations."
    ))
    user_msg = HumanMessage(content=f"Reviewer:\n{reviewer}\n\nArchitect:\n(Mermaid diagram generated)\n\nTester:\n{tester}")
    response = llm.invoke([prompt, user_msg])
    import time; time.sleep(10)
    return {"final_report": response.content, "current_agent": "synthesizer", "messages": [response]}

def apply_search_replace(repo_path: str, llm_output: str):
    import re, os
    
    # Fix common LLM hallucination where it puts >>>> before ====
    llm_output = re.sub(r'>>>>\s*====', '====', llm_output)
    
    blocks = llm_output.split('<<<<')
    current_file = None
    
    for i in range(1, len(blocks)):
        # Extract filename from the end of the previous text block
        pre_text = blocks[i-1].strip()
        if pre_text:
            lines = pre_text.split('\n')
            # Look at the last non-empty line
            for line in reversed(lines):
                line = line.strip().replace('*', '')
                if line and not line.startswith('>>>>'):
                    current_file = line
                    break
                    
        if not current_file:
            continue
            
        if '====' not in blocks[i] or '>>>>' not in blocks[i]:
            continue
            
        search_text = blocks[i].split('====')[0].strip('\r\n')
        replace_text = blocks[i].split('====')[1].split('>>>>')[0].strip('\r\n')
        
        filepath = os.path.join(repo_path, current_file)
        
        if not os.path.exists(filepath):
            # Try finding the file recursively
            for root, _, files in os.walk(repo_path):
                if current_file.split('/')[-1] in files:
                    filepath = os.path.join(root, current_file.split('/')[-1])
                    break
                    
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            content = content.replace('\r\n', '\n')
            search_text = search_text.replace('\r\n', '\n')
            replace_text = replace_text.replace('\r\n', '\n')
            
            if search_text in content:
                content = content.replace(search_text, replace_text, 1)
                with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(content)

def coder_node(state: AgentState):
    llm = get_llm()
    messages = state.get('messages', [])
    reviewer = state.get('reviewer_notes', '')
    repo_path = state.get('repo_path', '')
    
    prompt = SystemMessage(content=(
        "You are the DevSensei Auto-Fixer Coder Agent. "
        "Your task is to fix the bugs identified by the Reviewer. "
        "CRITICAL: You MUST use Search/Replace blocks to modify the code. "
        "Do NOT output full files. Only output the exact lines that need changing. "
        "Format exactly like this:\n"
        "script.js\n"
        "<<<<\n"
        "  countp1 = countp1 + 0.5;\n"
        "====\n"
        "  countp1 += 1;\n"
        ">>>>\n\n"
        "CRITICAL LIMITATION: The search block (<<<<) MUST be completely unique! You MUST include at least 3-4 lines of unchanged context above and below the edit so it doesn't accidentally match multiple places in the file."
    ))
    
    coder_messages = list(messages) + [HumanMessage(content=f"Here is the bug report to fix:\n\n{reviewer}")]
    
    response = llm.invoke([prompt] + coder_messages)
    llm_output = response.content
    
    # Try to apply the edits if we have a local path
    diff_output = ""
    if repo_path.startswith("/tmp/"):
        apply_search_replace(repo_path, llm_output)
        
        # Run git diff to show what changed, ignoring line-ending differences
        import subprocess, os, time, urllib.request, json
        try:
            result = subprocess.run(["git", "diff", "--ignore-space-at-eol", "--ignore-blank-lines"], cwd=repo_path, capture_output=True, text=True)
            diff_output = result.stdout
            
            if not diff_output:
                diff_output = "Edits were generated but the search strings didn't exactly match the file contents, or no files were changed."
            else:
                # Automate GitHub PR if token is available
                github_token = os.environ.get("GITHUB_TOKEN")
                pr_url = ""
                
                if github_token:
                    try:
                        # 1. Get original URL
                        origin_url = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=repo_path, capture_output=True, text=True).stdout.strip()
                        if "github.com" in origin_url:
                            # Extract owner/repo
                            repo_part = origin_url.split("github.com/")[-1].replace(".git", "")
                            
                            # 2. Inject token into remote
                            auth_url = f"https://{github_token}@github.com/{repo_part}.git"
                            subprocess.run(["git", "remote", "set-url", "origin", auth_url], cwd=repo_path, check=True)
                            
                            # 3. Branch, Commit, Push
                            branch_name = f"devsensei-autofix-{int(time.time())}"
                            subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_path, check=True)
                            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
                            
                            # Configure Git Identity
                            subprocess.run(["git", "config", "user.email", "coder@devsensei.ai"], cwd=repo_path, check=True)
                            subprocess.run(["git", "config", "user.name", "DevSensei AI"], cwd=repo_path, check=True)
                            
                            subprocess.run(["git", "commit", "-m", "DevSensei AI Auto-Fix"], cwd=repo_path, check=True)
                            subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=repo_path, check=True)
                            
                            # 4. Open PR via GitHub API
                            pr_data = {
                                "title": "DevSensei AI Auto-Fix: Code Refactoring",
                                "body": "This PR was automatically generated by the DevSensei Coder Agent.\n\n### Fixes Applied:\n```text\n" + llm_output[:1000] + "\n```",
                                "head": branch_name,
                                "base": "main" # assuming main is default
                            }
                            req = urllib.request.Request(f"https://api.github.com/repos/{repo_part}/pulls", data=json.dumps(pr_data).encode("utf-8"))
                            req.add_header("Authorization", f"token {github_token}")
                            req.add_header("Accept", "application/vnd.github.v3+json")
                            
                            with urllib.request.urlopen(req) as response:
                                pr_response = json.loads(response.read().decode())
                                pr_url = pr_response.get("html_url", "")
                    except Exception as pr_err:
                        diff_output += f"\n\n[Warning: Failed to automatically open GitHub PR: {str(pr_err)}]"
                
        except Exception as e:
            diff_output = f"Could not generate diff: {e}"
            
    final_output = f"### AI Generated Fixes\n\n```text\n{llm_output}\n```"
    if 'pr_url' in locals() and pr_url:
        final_output = f"🚀 **SUCCESS! Pull Request Automatically Opened:**\n[Click here to review and merge the PR on GitHub!]({pr_url})\n\n" + final_output
    elif diff_output:
        final_output += f"\n\n### Actual Applied Changes (Git Diff)\n\n```diff\n{diff_output}\n```"
        
    return {"final_report": final_output, "current_agent": "coder", "messages": [response]}
