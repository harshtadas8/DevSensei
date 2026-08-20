FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (git)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files and source code
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies using uv
RUN uv pip install --system -e .

# Run the FastAPI app
CMD ["uvicorn", "src.agent_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
