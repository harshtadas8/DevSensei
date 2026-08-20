from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import code_reviewer_node, architecture_node, tester_node, synthesizer_node

def build_graph():
    """
    Builds the multi-agent graph orchestrator for DevSensei.
    Flow: Reviewer -> Architect -> Tester -> Synthesizer -> END
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes (Agents)
    workflow.add_node("Reviewer", code_reviewer_node)
    workflow.add_node("Architect", architecture_node)
    workflow.add_node("Tester", tester_node)
    workflow.add_node("Synthesizer", synthesizer_node)
    
    # Define edges (Workflow sequence)
    workflow.add_edge(START, "Reviewer")
    workflow.add_edge("Reviewer", "Architect")
    workflow.add_edge("Architect", "Tester")
    workflow.add_edge("Tester", "Synthesizer")
    workflow.add_edge("Synthesizer", END)
    
    # Compile graph
    return workflow.compile()

# Singleton instance
devsensei_graph = build_graph()
