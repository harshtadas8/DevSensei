from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import code_reviewer_node, architecture_node, tester_node, synthesizer_node, coder_node

def should_continue(state: AgentState):
    """
    Agentic Routing: If the Reviewer finds a CRITICAL vulnerability, 
    divert to the Coder Agent to automatically fix it and open a PR.
    Otherwise, continue to the Synthesizer.
    """
    notes = state.get("reviewer_notes", "")
    if notes and "CRITICAL" in notes.upper():
        return "Coder"
    return "Synthesizer"

def build_graph():
    """
    Builds the multi-agent graph orchestrator for DevSensei.
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes (Agents)
    workflow.add_node("Reviewer", code_reviewer_node)
    workflow.add_node("Coder", coder_node)
    workflow.add_node("Architect", architecture_node)
    workflow.add_node("Tester", tester_node)
    workflow.add_node("Synthesizer", synthesizer_node)
    
    # Define edges (Workflow sequence with conditional routing)
    workflow.add_edge(START, "Architect")
    workflow.add_edge("Architect", "Tester")
    workflow.add_edge("Tester", "Reviewer")
    
    # The intelligent router:
    workflow.add_conditional_edges("Reviewer", should_continue, {
        "Coder": "Coder",
        "Synthesizer": "Synthesizer"
    })
    
    workflow.add_edge("Coder", END) # After fixing, we are completely done. Show the PR link!
    workflow.add_edge("Synthesizer", END)
    
    # Compile graph
    return workflow.compile()

# Singleton instance
devsensei_graph = build_graph()
