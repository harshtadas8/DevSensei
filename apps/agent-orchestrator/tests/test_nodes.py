import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from agent_orchestrator.agents.nodes import DummyLLM, planner_node
from langchain_core.messages import HumanMessage

def test_dummy_llm_responses():
    llm = DummyLLM()
    # Test architecture response
    resp = llm.invoke([HumanMessage(content="Architecture agent prompt")])
    assert "```mermaid" in resp.content
    
    # Test reviewer response
    resp = llm.invoke([HumanMessage(content="Reviewer prompt: Please review this code.")])
    assert "Security & Logic Review" in resp.content

def test_planner_node_state_update():
    # Provide a simple state and verify the planner populates things correctly
    state = {
        "messages": [HumanMessage(content="Review PR 42")],
        "repo_path": "./repo",
        "pr_number": 42,
        "current_agent": "system",
        "reviewer_notes": "",
        "architect_notes": "",
        "tester_notes": "",
        "final_report": ""
    }
    
    new_state = planner_node(state)
    assert new_state["current_agent"] == "planner"
    assert len(new_state["messages"]) > 1
    assert "System Planner initialized" in new_state["messages"][-1].content
