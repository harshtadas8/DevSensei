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
        # Use openai/gpt-oss-120b for robust formatting and reasoning
        return ChatGroq(temperature=0, model_name="openai/gpt-oss-120b", max_retries=2, request_timeout=30) 
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
    """
    Code Reviewer Agent: Focuses on logic bugs, security, and performance.
    """
    llm = get_llm()
    messages = state.get('messages', [])
    
    prompt = SystemMessage(content=(
        "You are the DevSensei Code Reviewer. "
        "Analyze the provided codebase for logic bugs, security vulnerabilities, and performance bottlenecks. "
        "Provide a detailed, bulleted markdown report. "
        "CRITICAL: You MUST provide an analysis. Do NOT output an empty string. "
        "Start your response EXACTLY with '# Security & Logic Review\n\n' and list your findings. "
        "CRITICAL: If you output any tables, you MUST use standard Markdown syntax with a mandatory separator row (e.g., | Col1 | Col2 |\n|---|---|)."
    ))
    
    # In a real run, we would pass the diff from the MCP server here
    response = llm.invoke([prompt] + list(messages))
    
    return {
        "reviewer_notes": response.content,
        "current_agent": "reviewer"
    }

def architecture_node(state: AgentState):
    """
    Architecture Agent: Focuses on structural integrity, patterns, and AST data.
    """
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
    
    return {
        "architect_notes": response.content,
        "current_agent": "architect"
    }

def tester_node(state: AgentState):
    """
    Test Generator Agent: Focuses on edge cases and test coverage.
    """
    llm = get_llm()
    messages = state.get('messages', [])
    
    prompt = SystemMessage(content=(
        "You are the DevSensei Test Generator. "
        "Based on the provided codebase, suggest missing unit tests, identify unhandled edge cases, "
        "and outline a comprehensive test plan using Markdown tables. "
        "CRITICAL: Do NOT output empty strings. Always provide a full test plan. "
        "CRITICAL: You MUST separate markdown table rows with actual line breaks (\\n). "
        "CRITICAL: All tables MUST include the mandatory separator row directly beneath the header (e.g. |---|---|)."
    ))
    
    response = llm.invoke([prompt] + list(messages))
    
    return {
        "tester_notes": response.content,
        "current_agent": "tester"
    }

def synthesizer_node(state: AgentState):
    """
    Synthesizer Agent: De-duplicates findings, formats markdown, ranks by severity.
    """
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
    
    return {
        "final_report": response.content,
        "current_agent": "synthesizer",
        "messages": [response]
    }
