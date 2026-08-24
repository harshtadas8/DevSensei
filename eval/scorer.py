import json
import os
import sys
import datetime
import re

# Append the orchestrator path so we can import the graph
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/agent-orchestrator/src")))

try:
    from agent_orchestrator.agents.graph import devsensei_graph
    from agent_orchestrator.agents.nodes import get_llm, _get_text
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    print("Warning: Could not import devsensei_graph. Ensure PYTHONPATH is set.")
    sys.exit(1)

def extract_findings_with_llm(reviewer_notes: str):
    """Uses LLM-as-a-judge to parse the unstructured reviewer notes into JSON."""
    if not reviewer_notes.strip():
        return []
        
    llm = get_llm()
    prompt = SystemMessage(content=(
        "You are an expert software evaluation judge. Read the provided code review report.\n"
        "Extract the issues identified in the report into a strict JSON list of objects.\n"
        "Each object MUST have exact keys: 'file', 'category'.\n"
        "Example: [{\"file\": \"src/db.py\", \"category\": \"security\"}]\n"
        "Output ONLY the raw JSON block wrapped in ```json ... ```, and nothing else."
    ))
    
    try:
        res = llm.invoke([prompt, HumanMessage(content=reviewer_notes)])
        text = _get_text(res)
        
        # Extract JSON block
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Fallback parse
        return json.loads(text)
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return []

def run_pipeline(patch_content):
    print("=> Invoking real LangGraph on patch...")
    initial_state = {
        "messages": [HumanMessage(content=f"Review this diff for security and logic bugs:\n```diff\n{patch_content}\n```")],
        "repo_path": "/tmp/test",
        "pr_number": 0,
        "current_agent": "system",
        "reviewer_notes": "",
        "architect_notes": "",
        "tester_notes": "",
        "final_report": "",
        "custom_rules": ""
    }
    
    # 1. Execute the actual graph
    final_state = devsensei_graph.invoke(initial_state)
    reviewer_notes = final_state.get("reviewer_notes", "")
    
    # 2. Extract structured findings for automated scoring
    return extract_findings_with_llm(reviewer_notes)

def score_eval():
    with open("eval/ground_truth.json", "r") as f:
        ground_truth = json.load(f)
        
    fixtures_dir = "eval/fixtures"
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    for filename, expected_findings in ground_truth.items():
        print(f"\nEvaluating fixture: {filename}")
        with open(os.path.join(fixtures_dir, filename), "r") as f:
            patch_content = f.read()
            
        actual_findings = run_pipeline(patch_content)
        
        # Match using (file, category)
        expected_set = {(f["file"], f["category"]) for f in expected_findings}
        actual_set = {(f.get("file", ""), f.get("category", "")) for f in actual_findings}
        
        for e in expected_set:
            if e in actual_set:
                true_positives += 1
            else:
                false_negatives += 1
                
        for a in actual_set:
            if a not in expected_set:
                false_positives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    print(f"\n--- DevSensei Evaluation Results ---")
    print(f"Precision: {precision:.2f}")
    print(f"Recall:    {recall:.2f}")
    print(f"F1 Score:  {f1:.2f}")
    
    trend_file = "eval/trend.csv"
    file_exists = os.path.isfile(trend_file)
    with open(trend_file, "a") as f:
        if not file_exists:
            f.write("timestamp,precision,recall,f1\n")
        f.write(f"{datetime.datetime.now().isoformat()},{precision:.2f},{recall:.2f},{f1:.2f}\n")
    
    with open("eval/results.json", "w") as f:
        json.dump({"precision": precision, "recall": recall, "f1": f1}, f)
    
    if recall < 0.8:
        print("FAIL: Recall dropped below 80% threshold!")
        sys.exit(1)
    if false_positives > 2:
        print("FAIL: Too many false positives (hallucinations)!")
        sys.exit(1)
        
    print("SUCCESS: Evaluation harness passed.")
    sys.exit(0)

if __name__ == "__main__":
    score_eval()
