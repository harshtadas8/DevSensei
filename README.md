[![DevSensei Enterprise Guardrails](https://github.com/username/DevSensei/actions/workflows/eval.yml/badge.svg)](https://github.com/username/DevSensei/actions/workflows/eval.yml)
# DevSensei

Agentic Codebase Intelligence & Automated Code Review, built on the Model Context Protocol (MCP).

## Overview
DevSensei has two faces:
1. **The Onboarder:** An interactive web dashboard that explains a codebase visually (Mermaid.js architecture diagrams) and textually via chat, citing exact file paths.
2. **The Code Reviewer:** An autonomous CI/CD pull request bot that reviews code with context-awareness, using specialized agents for Security, Style, and Test Coverage.

## Project Structure
This is a monorepo containing multiple services:
- `apps/frontend/`: Next.js web application for the Onboarder dashboard.
- `apps/agent-orchestrator/`: FastAPI backend serving the LangGraph agents.
- `apps/mcp-server/`: Python-based MCP Server exposing repository access tools to the LLMs.
- `apps/github-bot/`: Service handling GitHub webhooks and posting PR reviews.
- `infra/`: Infrastructure and deployment definitions.
- `eval/`: Evaluation harness and test fixtures for CI/CD gates.
- `docs/adr/`: Architecture Decision Records.

## Quickstart

### Prerequisites
- [Docker & Docker Compose](https://www.docker.com/)
- [uv](https://github.com/astral-sh/uv) (for Python tooling)
- [pnpm](https://pnpm.io/) (for Node tooling)
- Python 3.11+
- Node.js 20+

### Setup
1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in necessary API keys:
   ```bash
   cp .env.example .env
   ```
3. Start the local stack using Docker Compose:
   ```bash
   docker-compose up -d
   ```
4. Access the Onboarder Frontend at `http://localhost:3000`.
