import os
import asyncio
from typing import Optional, List, Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolRequest,
    ListToolsRequest,
    CallToolRequestParams,
    PaginatedRequestParams,
    CallToolResult,
    ListToolsResult,
    ServerCapabilities,
    ToolsCapability
)

# External libs
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

app = Server("devsensei-mcp")

# Environment flag for permission scoping
ENABLE_WRITE = os.environ.get("ENABLE_WRITE_TOOLS", "false").lower() == "true"

PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)

async def list_tools(*args, **kwargs) -> ListToolsResult:
    tools = [
        Tool(
            name="list_directory",
            description="Lists the contents of a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "depth": {"type": "integer", "default": 1}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="read_file_chunk",
            description="Read a line range from a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"}
                },
                "required": ["path", "start_line", "end_line"]
            }
        ),
        Tool(
            name="search_code",
            description="Search codebase for a keyword or regex.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string"}
                },
                "required": ["query", "path"]
            }
        ),
        Tool(
            name="get_git_diff",
            description="Get git diff for the current working directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string"}
                },
                "required": ["repo_path"]
            }
        ),
        Tool(
            name="get_file_history",
            description="Get git commit history for a specific file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string"},
                    "file_path": {"type": "string"}
                },
                "required": ["repo_path", "file_path"]
            }
        ),
        Tool(
            name="get_ast_data",
            description="Parse a Python file into an Abstract Syntax Tree structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"}
                },
                "required": ["file_path"]
            }
        )
    ]
    
    # Scoped Write Tools
    if ENABLE_WRITE:
        tools.append(
            Tool(
                name="post_pr_comment",
                description="Post a PR comment to GitHub.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pr_number": {"type": "integer"},
                        "body": {"type": "string"}
                    },
                    "required": ["pr_number", "body"]
                }
            )
        )
        
    return ListToolsResult(tools=tools)

async def call_tool(*args, **kwargs) -> CallToolResult:
    params = None
    for arg in args:
        if isinstance(arg, CallToolRequestParams):
            params = arg
            break
    if not params and 'params' in kwargs:
        params = kwargs['params']
    if not params:
        pass
    if len(args) == 2:
        params = args[1]
    elif len(args) == 1:
        req = args[0]
        params = getattr(req, "params", req)

    name = params.name
    tool_args = params.arguments or {}
    
    try:
        if name == "list_directory":
            path = tool_args.get("path")
            depth = tool_args.get("depth", 1)
            if not os.path.exists(path):
                return CallToolResult(content=[TextContent(type="text", text=f"Error: Path {path} does not exist.")])
            results = []
            for root, dirs, files in os.walk(path):
                level = root.replace(path, '').count(os.sep)
                if level >= depth:
                    dirs[:] = []
                    continue
                indent = ' ' * 4 * level
                results.append(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 4 * (level + 1)
                for f in files:
                    results.append(f"{subindent}{f}")
            return CallToolResult(content=[TextContent(type="text", text="\n".join(results))])

        elif name == "read_file_chunk":
            path = tool_args.get("path")
            start_line = tool_args.get("start_line")
            end_line = tool_args.get("end_line")
            if not os.path.exists(path):
                return CallToolResult(content=[TextContent(type="text", text=f"Error: File {path} does not exist.")])
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            chunk = lines[start_idx:end_idx]
            return CallToolResult(content=[TextContent(type="text", text="".join(chunk))])

        elif name == "search_code":
            query = tool_args.get("query")
            path = tool_args.get("path")
            if not os.path.exists(path):
                return CallToolResult(content=[TextContent(type="text", text=f"Error: Path {path} does not exist.")])
            matches = []
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for file in files:
                    if file.endswith('.py') or file.endswith('.ts') or file.endswith('.tsx') or file.endswith('.md'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                            for i, line in enumerate(lines):
                                if query in line:
                                    matches.append(f"{file_path}:{i+1} -> {line.strip()}")
                        except Exception:
                            pass
            return CallToolResult(content=[TextContent(type="text", text="\n".join(matches[:100]) or "No matches found.")])

        elif name == "get_git_diff":
            import git
            repo_path = tool_args.get("repo_path")
            repo = git.Repo(repo_path)
            diff = repo.git.diff()
            return CallToolResult(content=[TextContent(type="text", text=diff if diff else "No uncommitted changes.")])

        elif name == "get_file_history":
            import git
            repo_path = tool_args.get("repo_path")
            file_path = tool_args.get("file_path")
            repo = git.Repo(repo_path)
            log = repo.git.log("-n", "5", "--", file_path)
            return CallToolResult(content=[TextContent(type="text", text=log if log else "No history.")])

        elif name == "get_ast_data":
            file_path = tool_args.get("file_path")
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            tree = parser.parse(bytes(code, "utf8"))
            return CallToolResult(content=[TextContent(type="text", text=str(tree.root_node.sexp())[:1000])])

        elif name == "post_pr_comment":
            if not ENABLE_WRITE:
                return CallToolResult(content=[TextContent(type="text", text="Error: Write tools are currently disabled. Set ENABLE_WRITE_TOOLS=true to use this tool.", isError=True)])
            pr_number = tool_args.get("pr_number")
            body = tool_args.get("body")
            return CallToolResult(content=[TextContent(type="text", text=f"[DEV MODE] Successfully mocked posting comment to PR #{pr_number}:\n{body}")])

    except Exception as e:
        return CallToolResult(content=[TextContent(type="text", text=f"Error executing tool {name}: {str(e)}", isError=True)])

    return CallToolResult(content=[TextContent(type="text", text=f"Error: Unknown tool {name}", isError=True)])

# Register handlers
app.add_request_handler("tools/list", PaginatedRequestParams, list_tools)
app.add_request_handler("tools/call", CallToolRequestParams, call_tool)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio"], default="stdio")
    parser.add_argument("--enable-write", action="store_true", help="Enable write-operation tools")
    args = parser.parse_args()

    if args.enable_write:
        global ENABLE_WRITE
        ENABLE_WRITE = True

    async def run_stdio():
        async with stdio_server() as (read_stream, write_stream):
            init_options = app.create_initialization_options()
            init_options.capabilities = ServerCapabilities(tools=ToolsCapability(listChanged=False))
            await app.run(
                read_stream,
                write_stream,
                init_options
            )
    
    asyncio.run(run_stdio())

if __name__ == "__main__":
    main()
