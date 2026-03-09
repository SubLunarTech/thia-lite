#!/usr/bin/env python3
"""
Thia-Lite Simple IPC Server
============================
Simplified IPC server for Electron app.
Replaces MCP protocol with direct JSON-RPC for faster startup and better reliability.

No MCP protocol overhead - just simple request/response over stdio.
All existing tools are exposed with 100% feature parity.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SimpleIPCServer:
    """Simple JSON-RPC server for Electron IPC."""

    def __init__(self):
        self._tools = None
        self._handlers = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of tools to avoid import overhead."""
        if self._initialized:
            return

        from thia_lite.llm.tool_executor import _tool_registry, _tool_handlers
        from thia_lite.cli import _register_all_tools

        # Register all tools
        _register_all_tools()

        self._tools = _tool_registry
        self._handlers = _tool_handlers
        self._initialized = True

        logger.info(f"IPC Server initialized with {len(self._tools)} tools")

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC 2.0 request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            # Lazy initialization on first request
            self._ensure_initialized()

            # ── tools/list ───────────────────────────────────────────────────
            if method == "tools/list":
                tools_list = []
                for name, info in self._tools.items():
                    tools_list.append({
                        "name": name,
                        "description": info["description"],
                        "parameters": info["parameters"],
                    })
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools_list}
                }

            # ── tools/call ──────────────────────────────────────────────────
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})

                handler = self._handlers.get(tool_name)
                if not handler:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}",
                            "data": {"available_tools": list(self._handlers.keys())}
                        }
                    }

                try:
                    result = handler(tool_name, tool_args)
                    if asyncio.iscoroutine(result):
                        result = await result

                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": result,
                            "isError": False,
                        }
                    }
                except Exception as e:
                    logger.exception(f"Tool execution error ({tool_name}): {e}")
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": {"error": str(e), "tool": tool_name},
                            "isError": True,
                        }
                    }

            # ── ping ────────────────────────────────────────────────────────
            elif method == "ping":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"status": "ok", "server": "thia-lite-ipc"}
                }

            # ── initialize ──────────────────────────────────────────────────
            elif method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2.0",
                        "serverInfo": {
                            "name": "thia-lite",
                            "version": "0.1.0",
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }

            # ── Unknown method ──────────────────────────────────────────────
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

        except Exception as e:
            logger.exception(f"Request handling error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32700,
                    "message": f"Internal error: {e}"
                }
            }

    async def run_stdio(self):
        """
        Run IPC server on stdin/stdout.
        Simple line-by-line JSON protocol (no Content-Length framing).
        """
        logger.info("Simple IPC stdio server starting")

        # Use line buffering for immediate response
        # On Windows, flush after each write instead of relying on line buffering
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(line_buffering=True)
            except:
                # Fall back to explicit flushing on Windows
                pass

        try:
            while True:
                try:
                    # Read a line from stdin
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )

                    if not line:
                        logger.info("EOF received, stopping server")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    # Parse JSON request
                    try:
                        request = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {e}")
                        # Send error response
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {
                                "code": -32700,
                                "message": f"Parse error: {e}"
                            }
                        }
                        sys.stdout.write(json.dumps(error_response) + "\n")
                        sys.stdout.flush()
                        continue

                    # Handle request
                    response = await self.handle_request(request)

                    # Write response
                    if response is not None:
                        sys.stdout.write(json.dumps(response, default=str) + "\n")
                        sys.stdout.flush()

                except Exception as e:
                    logger.exception(f"Error in stdio loop: {e}")
                    # Try to send error response
                    try:
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {
                                "code": -32603,
                                "message": f"Internal error: {e}"
                            }
                        }
                        sys.stdout.write(json.dumps(error_response) + "\n")
                        sys.stdout.flush()
                    except:
                        pass

        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down")
        finally:
            logger.info("Simple IPC stdio server stopped")


def main():
    """Entry point for IPC mode."""
    import logging
    from thia_lite.config import get_settings

    # Setup logging
    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    server = SimpleIPCServer()
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
