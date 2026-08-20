# DevSensei Regression Caught by Eval Suite

During Phase 4 (Multi-Agent RAG), we attempted to optimize the Security Reviewer prompt by removing explicit instructions to look for N+1 query patterns and relying on the model's generalized knowledge. 

When we pushed the change, the GitHub Actions `DevSensei Enterprise Guardrails` workflow **FAILED**.
The eval scorer (`eval/scorer.py`) reported that Recall dropped to 66% (below our 80% threshold).

Looking at the test reports, the `pr_3_n_plus_one.patch` fixture (which contains a loop performing database lookups) was falsely marked as clean.

We reverted the prompt change, and the CI gate returned to green. This proves that our CI/CD Evaluation Harness successfully gates bad prompts from reaching production, operating exactly like a traditional unit test suite but for LLM behavior.
