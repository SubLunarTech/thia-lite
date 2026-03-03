"""
Thia-Lite MCP Client
======================
Connect to external MCP servers (thia-libre, data connectors, etc.)
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Client to connect to external MCP servers."""

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30)
        self._request_id = 0
        self.server_info: Optional[Dict] = None
        self.tools: List[Dict] = []

    async def close(self):
        await self._client.aclose()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send(self, method: str, params: Dict = None) -> Dict:
        """Send a JSON-RPC request."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params:
            payload["params"] = params

        resp = await self._client.post(f"{self.url}/mcp", json=payload)
        resp.raise_for_status()
        return resp.json().get("result", {})

    async def initialize(self) -> bool:
        """Initialize the MCP connection."""
        try:
            result = await self._send("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "thia-lite", "version": "0.1.0"},
            })
            self.server_info = result.get("serverInfo", {})
            logger.info(f"Connected to MCP server: {self.server_info.get('name', self.name)}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.name}: {e}")
            return False

    async def list_tools(self) -> List[Dict]:
        """List available tools from the server."""
        try:
            result = await self._send("tools/list")
            self.tools = result.get("tools", [])
            return self.tools
        except Exception as e:
            logger.error(f"Failed to list tools from {self.name}: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on the remote server."""
        try:
            result = await self._send("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                try:
                    return json.loads(content[0]["text"])
                except json.JSONDecodeError:
                    return content[0]["text"]
            return result
        except Exception as e:
            logger.error(f"Tool call failed ({tool_name}): {e}")
            return {"error": str(e)}


class MCPClientManager:
    """Manage multiple MCP client connections."""

    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}

    async def add_server(self, name: str, url: str) -> bool:
        """Add and connect to an MCP server."""
        client = MCPClient(name, url)
        if await client.initialize():
            await client.list_tools()
            self.clients[name] = client
            logger.info(f"Added MCP server '{name}' with {len(client.tools)} tools")
            return True
        return False

    async def remove_server(self, name: str):
        """Disconnect from an MCP server."""
        if name in self.clients:
            await self.clients[name].close()
            del self.clients[name]

    def get_all_tools(self) -> List[Dict]:
        """Get all tools from all connected servers."""
        tools = []
        for name, client in self.clients.items():
            for tool in client.tools:
                tool_copy = tool.copy()
                tool_copy["server"] = name
                tools.append(tool_copy)
        return tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on a specific server."""
        client = self.clients.get(server_name)
        if not client:
            return {"error": f"Unknown server: {server_name}"}
        return await client.call_tool(tool_name, arguments)

    async def close_all(self):
        """Close all connections."""
        for client in self.clients.values():
            await client.close()
        self.clients.clear()
