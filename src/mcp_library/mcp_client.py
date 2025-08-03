import asyncio
import json
import os
import structlog
from typing import Dict, Any, Optional, List
from enum import Enum

from src.mcp_library.client import JsonRpcClient
from src.mcp_library.transport import SubprocessTransport, JsonRpcTransport

logger = structlog.get_logger()

class ProtocolVersion(Enum):
    """Known MCP protocol versions."""
    V0_1_0 = "0.1.0"
    V2024_11_05 = "2024-11-05"
    V2025_06_18 = "2025-06-18"

class MCPClient(JsonRpcClient):
    """An MCP-specific JSON-RPC client."""
    def __init__(self, transport: JsonRpcTransport, 
                 protocol_version: ProtocolVersion = ProtocolVersion.V2025_06_18,
                 client_info: Optional[Dict[str, str]] = None):
        super().__init__(transport)
        self.protocol_version = protocol_version
        self.client_info = client_info or {"name": "mcp-client", "version": "0.1.0"}
        self.server_info: Optional[Dict[str, Any]] = None
        self.available_tools: List[str] = []

    async def initialize(self) -> Dict[str, Any]:
        """Initializes the MCP session."""
        params = {
            "protocolVersion": self.protocol_version.value,
            "capabilities": {},
            "clientInfo": self.client_info
        }
        result = await self.request("initialize", params)
        self.server_info = result.get("serverInfo")
        logger.info("MCP session initialized", server_info=self.server_info)
        await self.notify("notifications/initialized")
        await self.list_tools()
        return result

    async def list_tools(self) -> List[str]:
        """Lists available tools on the server."""
        result = await self.request("tools/list", {})
        tools = result.get("tools", [])
        self.available_tools = [tool.get("name", "") for tool in tools]
        logger.info("Available tools updated", tools=self.available_tools)
        return self.available_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Calls a tool on the server."""
        if tool_name not in self.available_tools:
            logger.warning("Attempting to call a tool not listed by the server.", tool_name=tool_name)
        
        params = {"name": tool_name, "arguments": arguments}
        return await self.request("tools/call", params)

class MCPServerLauncher:
    """A helper class to launch MCP-compatible servers."""
    @staticmethod
    async def launch_supabase(project_ref: str, access_token: str) -> MCPClient:
        """Launches the Supabase MCP server and returns an initialized client."""
        logger.info("Launching Supabase MCP server...", project_ref=project_ref)
        process = await asyncio.create_subprocess_exec(
            "npx", "-y", "@supabase/mcp-server-supabase@latest",
            "--project-ref", project_ref,
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, # Capture stderr
            env={**os.environ, "SUPABASE_ACCESS_TOKEN": access_token}
        )
        transport = SubprocessTransport(process)
        client = MCPClient(transport)
        
        # Start the client and initialize the connection
        await client.start()
        await asyncio.sleep(2) # Allow server to start up
        await client.initialize()
        return client

class SupabaseMCPWrapper:
    """A type-safe wrapper for Supabase-specific MCP tool calls."""
    def __init__(self, client: MCPClient):
        self.client = client

    async def execute_sql(self, query: str) -> Any:
        """Executes a SQL query."""
        result = await self.client.call_tool("execute_sql", {"query": query})
        # The actual data is often in a nested 'text' field within 'content'
        if isinstance(result, dict) and "content" in result:
            for item in result["content"]:
                if item.get("type") == "text":
                    try:
                        return json.loads(item["text"])
                    except json.JSONDecodeError:
                        return item["text"] # Return as-is if not JSON
        return result # Fallback
