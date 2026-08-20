# Contributing to DevSensei

## Monorepo Workflow

### 1. Pre-commit Hooks
We use `pre-commit` to ensure code formatting and quality before commits are created. 
Install it locally:
```bash
pip install pre-commit
pre-commit install
```
This runs `ruff` (for Python) and `prettier` (for JS/TS/JSON/Markdown) on every commit.

### 2. Branching Convention
Use the following prefixes for your branches:
- `feat/`: A new feature
- `fix/`: A bug fix
- `docs/`: Documentation only changes
- `refactor/`: A code change that neither fixes a bug nor adds a feature
- `test/`: Adding missing tests or correcting existing tests
- `chore/`: Changes to the build process or auxiliary tools

Example: `feat/mcp-read-file-tool`

### 3. Commit Convention
We follow [Conventional Commits](https://www.conventionalcommits.org/).

### 4. Architecture Decision Records (ADRs)
Any significant architectural change should be documented in `docs/adr/` using a lightweight Markdown template.
