import operator
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    The state of our DevSensei LangGraph.
    Tracks the conversational messages and analysis results.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    repo_path: str
    pr_number: int | None
    custom_rules: str
    
    # Internal agent tracking
    current_agent: str
    reviewer_notes: str
    architect_notes: str
    tester_notes: str
    
    # Final output
    final_report: str
