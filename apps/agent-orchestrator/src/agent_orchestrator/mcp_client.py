import asyncio
from contextlib import AsyncExitStack
from typing import List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class DevSenseiMCPClient:
    """
    Connects the Agent Orchestrator to the Phase 1 MCP Server.
    """
    def __init__(self, server_script_path: str = "/mcp-server/src/mcp_server/server.py"):
        self.server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
        )
        self.stack = AsyncExitStack()
        self.session = None

    async def connect(self):
        # Initialize standard IO transport
        transport_ctx = stdio_client(self.server_params)
        read_stream, write_stream = await self.stack.enter_async_context(transport_ctx)
        
        # Initialize Client Session
        self.session = await self.stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        return self.session

    async def get_available_tools(self) -> List[dict]:
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(self, name: str, arguments: dict):
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        result = await self.session.call_tool(name, arguments)
        return result

    async def cleanup(self):
        await self.stack.aclose()
