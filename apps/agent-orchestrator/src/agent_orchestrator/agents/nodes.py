from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from .state import AgentState
import os

from langchain_core.globals import set_llm_cache
from langchain_core.caches import InMemoryCache

# Enable in-memory caching to save API tokens and speed up redundant requests
set_llm_cache(InMemoryCache())

# Helper to get the LLM (Supports Groq for free tier, Gemini as fallback)
# Dummy LLM fallback for safe local testing without API keys (and for CI/CD)
class DummyLLM:
    def invoke(self, messages):
        text = " ".join([str(m.content) for m in messages])
        # If this is the Code Reviewer parsing the diff:
        if "Review this diff" in text:
            if "SELECT * FROM users WHERE username = '{username}'" in text:
                return AIMessage(content="# Security & Logic Review\n* **CRITICAL**: SQL Injection found.")
            elif "posts.extend(detailed_posts)" in text:
                return AIMessage(content="# Security & Logic Review\n* **CRITICAL**: N+1 query found.")
            else:
                return AIMessage(content="# Security & Logic Review\nEverything looks good.")
        
        if "Architecture" in text or "Mermaid" in text:
            return AIMessage(content="""```mermaid
graph TD
    A[Next.js Frontend] -->|REST| B(FastAPI Orchestrator)
    B -->|Triggers| C{LangGraph Agents}
    C -->|Reviewer| D[Security & Logic]
    C -->|Architect| E[Architecture Design]
    C -->|Tester| F[Unit Tests]
    C -->|Synthesizer| G[Final Markdown Report]
    
    C <-->|Retrieves Context| H[(ChromaDB Vector Store)]
    H <-->|Indexed by| I[Tree-sitter AST Parser]
```""")

        # Fallback response for Coder, Tester, Synthesizer
        return AIMessage(content="[LLM Mock] Analysis complete. Add an API key to your .env to see real insights!")

def get_llm():
    if os.environ.get("GROQ_API_KEY"):
        # Use a valid Groq model
        return ChatGroq(temperature=0, model_name="openai/gpt-oss-120b", max_retries=10, request_timeout=60) 
    elif os.environ.get("GOOGLE_API_KEY"):
        return ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
        
    return DummyLLM()

def _get_text(response):
    content = getattr(response, 'content', response)
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "\n".join([str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content])
    return str(content)

def _format_mcp_tool(tool):
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema
        }
    }

from agent_orchestrator.mcp_client import DevSenseiMCPClient

async def code_reviewer_node(state: AgentState):
    llm = get_llm()
    messages = state.get('messages', [])
    repo_path = state.get('repo_path', "")
    custom_rules = state.get('custom_rules', "")
    rules_prompt = f"\n\nCRITICAL TEAM RULES TO ENFORCE:\n{custom_rules}\n(You must enforce these team rules during your code review if applicable.)\n" if custom_rules else ""

    prompt = SystemMessage(content=(
        "You are the DevSensei Code Reviewer. "
        "Analyze the provided codebase for logic bugs, security vulnerabilities, and performance bottlenecks. "
        "Provide a concise, bulleted markdown report. Limit your report to the TOP 5 most critical issues to save tokens. "
        "CRITICAL: You MUST provide an analysis. Do NOT output an empty string. "
        "Start your response EXACTLY with '# Security & Logic Review\n\n' and list your findings. "
        "CRITICAL: If you output any tables, you MUST use standard Markdown syntax with a mandatory separator row (e.g., | Col1 | Col2 |\n|---|---)."
        f"IMPORTANT: You have access to MCP tools to search the codebase and read files. The codebase is located at: {repo_path}. If the provided diff references files or functions you do not fully understand, USE YOUR TOOLS to fetch the surrounding context BEFORE completing your review."
        f"{rules_prompt}"
    ))
    
    if repo_path and not isinstance(llm, DummyLLM):
        import os
        mcp_script_docker = "/mcp-server/src/mcp_server/server.py"
        if os.path.exists(mcp_script_docker):
            mcp_script = mcp_script_docker
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
            mcp_script = os.path.join(base_dir, "apps", "mcp-server", "src", "mcp_server", "server.py")
        
        mcp = DevSenseiMCPClient(server_script_path=mcp_script)
        await mcp.connect()
        try:
            tools = await mcp.get_available_tools()
            lc_tools = [_format_mcp_tool(t) for t in tools]
            llm_with_tools = llm.bind_tools(lc_tools)
            
            # Start message chain
            current_messages = list(messages)
            ai_msg = await llm_with_tools.ainvoke([prompt] + current_messages)
            
            # Allow up to 3 iterative tool calls mid-reasoning
            for i in range(3):
                if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                    current_messages.append(ai_msg)
                    for call in ai_msg.tool_calls:
                        print(f"🤖 [Agentic Action] LLM decided to use MCP Tool: {call['name']} with args: {call['args']}", flush=True)
                        tool_result = await mcp.call_tool(call["name"], call["args"])
                        # Using ToolMessage requires correct import

                        current_messages.append(ToolMessage(content=str(tool_result), tool_call_id=call["id"], name=call["name"]))
                    
                    if i == 2:
                        # Force a final text answer by removing tool bindings

                        force_msg = HumanMessage(content="You have reached the tool execution limit. Please provide your final Reviewer Notes now based on the information you have. Do not attempt to call any more tools.")
                        ai_msg = await llm.ainvoke([prompt] + current_messages + [force_msg])
                    else:
                        ai_msg = await llm_with_tools.ainvoke([prompt] + current_messages)
                else:
                    break
            response = ai_msg
        finally:
            await mcp.cleanup()
    else:
        # Standard fallback for DummyLLM or missing repo
        response = llm.invoke([prompt] + list(messages))
        
    return {"reviewer_notes": _get_text(response), "current_agent": "reviewer"}

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
    
    return {"architect_notes": _get_text(response), "current_agent": "architect"}

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
    
    return {"tester_notes": _get_text(response), "current_agent": "tester"}

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
    
    return {"final_report": _get_text(response), "current_agent": "synthesizer", "messages": [response]}

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
            
        # Check for at least 4 equals signs
        if not re.search(r'={4,}', blocks[i]) or '>>>>' not in blocks[i]:
            continue
            
        parts = re.split(r'={4,}', blocks[i], maxsplit=1)
        search_text = parts[0].strip('\r\n')
        replace_text = parts[1].split('>>>>')[0].strip('\r\n')
        
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

async def coder_node(state: AgentState):
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
        "CRITICAL LIMITATION 1: The search block (<<<<) MUST be completely unique! Include 3-4 lines of unchanged context above and below the edit.\n"
        "CRITICAL LIMITATION 2: DO NOT USE DIFF MARKERS! Never use '+' or '-' at the start of lines. The text inside <<<< MUST exactly match the file byte-for-byte.\n"
        f"IMPORTANT: You have access to MCP tools to search the codebase and read files. The codebase is located at: {repo_path}. USE YOUR TOOLS to read the exact file contents before generating your search/replace block to ensure your search block perfectly matches the file."
    ))
    
    coder_messages = list(messages) + [HumanMessage(content=f"Here is the bug report to fix:\n\n{reviewer}")]
    
    if repo_path and not isinstance(llm, DummyLLM):
        import os
        mcp_script_docker = "/mcp-server/src/mcp_server/server.py"
        if os.path.exists(mcp_script_docker):
            mcp_script = mcp_script_docker
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
            mcp_script = os.path.join(base_dir, "apps", "mcp-server", "src", "mcp_server", "server.py")
        
        mcp = DevSenseiMCPClient(server_script_path=mcp_script)
        await mcp.connect()
        try:
            tools = await mcp.get_available_tools()
            lc_tools = [_format_mcp_tool(t) for t in tools]
            llm_with_tools = llm.bind_tools(lc_tools)
            
            # Start message chain
            current_messages = list(coder_messages)
            ai_msg = await llm_with_tools.ainvoke([prompt] + current_messages)
            
            # Allow up to 3 iterative tool calls mid-reasoning
            for i in range(3):
                if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                    current_messages.append(ai_msg)
                    for call in ai_msg.tool_calls:
                        print(f"🤖 [Agentic Action] LLM decided to use MCP Tool: {call['name']} with args: {call['args']}", flush=True)
                        tool_result = await mcp.call_tool(call["name"], call["args"])

                        current_messages.append(ToolMessage(content=str(tool_result), tool_call_id=call["id"], name=call["name"]))
                    
                    if i == 2:

                        force_msg = HumanMessage(content="You have reached the tool execution limit. Please provide your final search and replace block now based on the information you have. Do not attempt to call any more tools.")
                        ai_msg = await llm.ainvoke([prompt] + current_messages + [force_msg])
                    else:
                        ai_msg = await llm_with_tools.ainvoke([prompt] + current_messages)
                else:
                    break
            response = ai_msg
        finally:
            await mcp.cleanup()
    else:
        response = llm.invoke([prompt] + coder_messages)
        
    llm_output = _get_text(response)
    
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
                github_token = os.environ.get("GITHUB_TOKEN", "").strip()
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
                    except urllib.error.HTTPError as pr_err:
                        error_body = pr_err.read().decode()
                        diff_output += f"\n\n[Warning: Failed to automatically open GitHub PR. HTTP {pr_err.code}: {error_body}]"
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
