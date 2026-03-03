"""
Thia-Lite MCP Server
======================
Expose all astrology tools via Model Context Protocol (MCP).
Supports stdio (for Claude Desktop / Pi) and HTTP modes.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# MCP Protocol version
MCP_VERSION = "2024-11-05"


# ─── JSON-RPC Helpers ─────────────────────────────────────────────────────────

def _jsonrpc_response(id: Any, result: Any) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _jsonrpc_error(id: Any, code: int, message: str) -> Dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _jsonrpc_notification(method: str, params: Any = None) -> Dict:
    msg = {"jsonrpc": "2.0", "method": method}
    if params:
        msg["params"] = params
    return msg


# ─── MCP Request Handler ─────────────────────────────────────────────────────

async def handle_mcp_request(request: Dict) -> Dict:
    """Handle a single MCP JSON-RPC request."""
    from thia_lite.llm.tool_executor import _tool_registry, _tool_handlers

    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    # ── initialize ────────────────────────────────────────────────────────
    if method == "initialize":
        return _jsonrpc_response(req_id, {
            "protocolVersion": MCP_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "thia-lite",
                "version": "0.1.0",
            },
        })

    # ── ping ──────────────────────────────────────────────────────────────
    if method == "ping":
        return _jsonrpc_response(req_id, {})

    # ── notifications/initialized ─────────────────────────────────────────
    if method == "notifications/initialized":
        return None  # No response needed for notifications

    # ── tools/list ────────────────────────────────────────────────────────
    if method == "tools/list":
        tools = []
        for name, info in _tool_registry.items():
            tools.append({
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": info["parameters"].get("properties", {}),
                    "required": info["parameters"].get("required", []),
                },
            })
        return _jsonrpc_response(req_id, {"tools": tools})

    # ── tools/call ────────────────────────────────────────────────────────
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = _tool_handlers.get(tool_name)
        if not handler:
            return _jsonrpc_error(req_id, -32601, f"Unknown tool: {tool_name}")

        try:
            result = handler(tool_name, tool_args)
            if asyncio.iscoroutine(result):
                result = await result

            # MCP tools/call returns content array
            return _jsonrpc_response(req_id, {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, default=str),
                }],
                "isError": False,
            })
        except Exception as e:
            return _jsonrpc_response(req_id, {
                "content": [{
                    "type": "text",
                    "text": json.dumps({"error": str(e)}),
                }],
                "isError": True,
            })

    # ── Unknown method ────────────────────────────────────────────────────
    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


# ─── stdio Server ─────────────────────────────────────────────────────────────

async def run_stdio_server():
    """
    Run MCP server on stdin/stdout.
    This is how Claude Desktop and Pi connect.
    """
    logger.info("MCP stdio server starting")

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

    buffer = ""

    while True:
        try:
            line = await reader.readline()
            if not line:
                break

            text = line.decode("utf-8").strip()
            if not text:
                continue

            # Handle Content-Length header (LSP-style framing)
            if text.startswith("Content-Length:"):
                content_length = int(text.split(":")[1].strip())
                await reader.readline()  # Empty line separator
                body = await reader.readexactly(content_length)
                text = body.decode("utf-8")

            try:
                request = json.loads(text)
            except json.JSONDecodeError:
                buffer += text
                try:
                    request = json.loads(buffer)
                    buffer = ""
                except json.JSONDecodeError:
                    continue

            response = await handle_mcp_request(request)

            if response is not None:
                response_text = json.dumps(response)
                # Write with Content-Length framing
                header = f"Content-Length: {len(response_text)}\r\n\r\n"
                writer.write(header.encode("utf-8"))
                writer.write(response_text.encode("utf-8"))
                await writer.drain()

        except Exception as e:
            logger.error(f"stdio server error: {e}")
            break

    logger.info("MCP stdio server stopped")


# ─── HTTP Server ──────────────────────────────────────────────────────────────

async def run_http_server(port: int = 8443):
    """Run MCP server over HTTP (SSE transport)."""
    try:
        from aiohttp import web
    except ImportError:
        logger.error("aiohttp required for HTTP mode: pip install aiohttp")
        return

    async def handle_post(request):
        body = await request.json()
        response = await handle_mcp_request(body)
        if response:
            return web.json_response(response)
        return web.Response(status=204)

    async def handle_health(request):
        return web.json_response({"status": "ok", "server": "thia-lite-mcp"})

    app = web.Application()
    app.router.add_post("/mcp", handle_post)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"MCP HTTP server running on http://0.0.0.0:{port}")

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await runner.cleanup()
