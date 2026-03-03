"""
Thia-Lite HTTP API Server
===========================
Lightweight REST API for the Electron desktop frontend.
Uses only Python stdlib — zero added dependencies.

Endpoints:
    GET  /health                       → System health check
    POST /chat                         → Send message, get response
    GET  /conversations                → List recent conversations
    GET  /conversations/:id/messages   → Get messages for a conversation

Runs on port 8765 (matching desktop/src/app.js API_BASE).
"""

import os
import sys
import logging
import asyncio
import threading
import json
import re
from typing import Optional, Any, Dict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Ensure log directory exists
LOG_DIR = os.path.expanduser("~/.thia-lite/logs")
os.makedirs(LOG_DIR, exist_ok=True)
STARTUP_LOG = os.path.join(LOG_DIR, "api_server_startup.log")

# Early logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(STARTUP_LOG),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.info("Initializing Thia API Server...")

DEFAULT_PORT = 8765

# ─── Lazy singletons ─────────────────────────────────────────────────────────

_manager = None
_tools_registered = False
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a persistent background event loop for async calls."""
    global _loop, _loop_thread
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _loop


def _run_async(coro):
    """Run an async coroutine on the background loop and return the result."""
    loop = _get_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=120)


def _get_manager():
    """Get or create the shared ConversationManager."""
    global _manager, _tools_registered
    if not _tools_registered:
        _register_tools()
        _tools_registered = True
    if _manager is None:
        from thia_lite.llm.conversation import ConversationManager
        _manager = ConversationManager()
    return _manager


def _register_tools():
    """Register all tool engines (same as CLI._register_all_tools)."""
    from thia_lite.llm.tool_executor import register_memory_tools
    _safe_import("thia_lite.engines.astrology", "register_astrology_tools")
    try:
        register_memory_tools()
    except Exception as e:
        logger.warning("Could not register memory tools: %s", e)
    _safe_import("thia_lite.engines.autonomy", "register_autonomy_tools")
    _safe_import("thia_lite.engines.ported_tools", "register_ported_tools")
    _safe_import("thia_lite.engines.verification", "register_verification_tools")
    _safe_import("thia_lite.engines.chart_renderer", "register_chart_tools")


def _safe_import(module: str, func_name: str):
    """Import a module and call its registration function, logging failures."""
    try:
        mod = __import__(module, fromlist=[func_name])
        getattr(mod, func_name)()
    except Exception as e:
        logger.warning("Could not register %s.%s: %s", module, func_name, e)


# ─── URL routing ──────────────────────────────────────────────────────────────

_CONV_MSG_RE = re.compile(r"^/conversations/([^/]+)/messages$")


# ─── Request Handler ─────────────────────────────────────────────────────────

class ThiaRequestHandler(BaseHTTPRequestHandler):
    """Handle REST requests for the Electron desktop frontend."""

    # Suppress default stderr logging (we use our own logger)
    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)

    # ── CORS ──────────────────────────────────────────────────────────────

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw)

    def _send_error(self, status: int, message: str):
        self._send_json({"error": message}, status)

    # ── GET routes ────────────────────────────────────────────────────────

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/health" or path == "":
            return self._handle_health()
        elif path == "/conversations":
            return self._handle_list_conversations()
        elif path == "/update/check":
            return self._handle_update_check()
        else:
            m = _CONV_MSG_RE.match(path)
            if m:
                return self._handle_get_messages(m.group(1))
        self._send_error(404, f"Not found: {path}")

    # ── POST routes ───────────────────────────────────────────────────────

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/chat":
            return self._handle_chat()
        elif path == "/update/apply":
            return self._handle_update_apply()
        self._send_error(404, f"Not found: {path}")

    # ── Endpoint Implementations ──────────────────────────────────────────

    def _handle_health(self):
        from thia_lite.llm.tool_executor import get_tool_names
        self._send_json({
            "status": "ok",
            "tools": len(get_tool_names()),
            "tool_names": get_tool_names()[:10],
        })

    def _handle_list_conversations(self):
        mgr = _get_manager()
        convs = mgr.list_conversations()
        self._send_json(convs)

    def _handle_get_messages(self, conversation_id: str):
        from thia_lite.db import get_db
        db = get_db()
        messages = db.get_conversation_messages(conversation_id)
        self._send_json(messages)

    def _handle_chat(self):
        try:
            body = self._read_json()
        except (json.JSONDecodeError, ValueError) as e:
            return self._send_error(400, f"Invalid JSON: {e}")

        message = body.get("message", "").strip()
        if not message:
            return self._send_error(400, "Missing 'message' field")

        conversation_id = body.get("conversation_id")

        mgr = _get_manager()

        # Resume or start conversation
        if conversation_id:
            mgr.load_conversation(conversation_id)
        elif mgr.current_conversation_id is None:
            title = message[:50] + "..." if len(message) > 50 else message
            mgr.new_conversation(title)

        provider = body.get("provider")
        api_key = body.get("api_key")
        model = body.get("model")
        temperature = body.get("temperature")

        try:
            result = _run_async(mgr.send_message(
                message, 
                provider=provider, 
                api_key=api_key, 
                model=model, 
                temperature=temperature
            ))
            result["conversation_id"] = mgr.current_conversation_id
            self._send_json(result)
        except Exception as e:
            logger.exception("Chat error")
            self._send_error(500, str(e))

    def _handle_update_check(self):
        try:
            from thia_lite import __version__
            from thia_lite.updater import check_for_updates
            update = _run_async(check_for_updates(__version__))
            if update:
                self._send_json({"available": True, "current": __version__, **update})
            else:
                self._send_json({"available": False, "current": __version__})
        except Exception as e:
            self._send_json({"available": False, "error": str(e)})

    def _handle_update_apply(self):
        try:
            from thia_lite.updater import update_from_git
            success, message = update_from_git()
            self._send_json({"success": success, "message": message})
        except Exception as e:
            self._send_error(500, str(e))


# ─── Server startup ──────────────────────────────────────────────────────────

def run_server(port: int = DEFAULT_PORT):
    """Start the HTTP API server."""
    # Register all tools first
    _get_manager()

    server = ThreadingHTTPServer(("0.0.0.0", port), ThiaRequestHandler)
    logger.info("Thia API server listening on http://0.0.0.0:%d", port)
    print(f"✦ Thia API server ready on http://localhost:{port}")
    print(f"  Endpoints: /health, /chat, /conversations")
    print(f"  Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✦ Server stopped.")
    finally:
        server.server_close()
        if _loop and not _loop.is_closed():
            _loop.call_soon_threadsafe(_loop.stop)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_server(port)
