import sys
from .indexer import index_repository

def run():
    if len(sys.argv) < 2:
        print("Usage: python -m agent_orchestrator.ingestion.cli <path_to_repo>")
        sys.exit(1)
        
    repo_path = sys.argv[1]
    print(f"Starting ingestion for repository: {repo_path}")
    index_repository(repo_path)

if __name__ == "__main__":
    run()
