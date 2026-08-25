import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from agent_orchestrator.agents.nodes import DummyLLM, code_reviewer_node
from agent_orchestrator.agents.graph import should_continue
from langchain_core.messages import HumanMessage

def test_dummy_llm_responses():
    llm = DummyLLM()
    # Test architecture response
    resp = llm.invoke([HumanMessage(content="Tell me about the Architecture")])
    assert "```mermaid" in resp.content
    
    # Test reviewer response with a critical bug
    resp = llm.invoke([HumanMessage(content="Review this diff\nSELECT * FROM users WHERE username = '{username}'")])
    assert "CRITICAL" in resp.content
    assert "SQL Injection" in resp.content
    
    # Test reviewer response with clean code
    resp = llm.invoke([HumanMessage(content="Review this diff\nx = 1 + 1")])
    assert "Everything looks good" in resp.content

def test_conditional_routing():
    # If the reviewer found a CRITICAL issue, it should route to the coder agent
    state_critical = {"reviewer_notes": "* **CRITICAL**: SQL Injection found."}
    assert should_continue(state_critical) == "Coder"
    
    # If the reviewer found no critical issues, it should route to the synthesizer
    state_clean = {"reviewer_notes": "Everything looks good."}
    assert should_continue(state_clean) == "Synthesizer"
