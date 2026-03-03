"""
Thia-Lite Tool Executor — Agentic Loop
========================================
The core agentic loop: LLM generates tool calls → executor runs them
against local engines → results fed back to the LLM.

This mirrors the Claude Code / Claude Desktop pattern.
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from thia_lite.llm.ollama_client import OllamaClient, make_ollama_tool, get_ollama_client

logger = logging.getLogger(__name__)

# ─── Tool Registry ────────────────────────────────────────────────────────────

_tool_registry: Dict[str, Dict[str, Any]] = {}
_tool_handlers: Dict[str, Callable] = {}


def register_tool(name: str, description: str, parameters: Dict[str, Any],
                   handler: Callable) -> None:
    """Register a tool with its handler function."""
    _tool_registry[name] = {
        "name": name,
        "description": description,
        "parameters": parameters,
    }
    _tool_handlers[name] = handler


def get_all_tools() -> List[Dict[str, Any]]:
    """Get all registered tools in Ollama format."""
    return [
        make_ollama_tool(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"],
        )
        for t in _tool_registry.values()
    ]


def get_tool_names() -> List[str]:
    """Get all registered tool names."""
    return list(_tool_registry.keys())


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Thia, an expert AI astrology assistant powered by the Swiss Ephemeris.
You have access to tools for calculating natal charts, transits, elections, timing techniques,
and more. You produce precise, professional astrological analysis.

Key principles:
- Always use tools for astronomical calculations — never guess planetary positions
- When a user asks about astrology, use the appropriate tool to calculate first, then interpret
- For natal charts, you need: date, time, latitude, longitude (ask if not provided)
- Use geocode_location to convert place names to coordinates
- Be specific about degrees, signs, houses, and aspects
- Reference traditional sources (Ptolemy, William Lilly) when relevant
- Present results clearly with both technical data and accessible interpretation

Available rule sources: William Lilly (Christian Astrology, 1647) and Ptolemy (Tetrabiblos).
Use astrology_rules_rag_search to find relevant traditional rules for your interpretations.

You are running locally — all data stays on the user's machine. No external APIs are called
for calculations."""


# ─── Agentic Executor ─────────────────────────────────────────────────────────

class ToolExecutor:
    """
    Agentic tool execution loop.

    Flow:
    1. User sends message
    2. LLM receives message + tool definitions
    3. If LLM returns tool_calls → execute them → feed results back → goto 2
    4. If LLM returns text → return to user
    """

    def __init__(self, client: Optional[OllamaClient] = None,
                 max_iterations: int = 10,
                 system_prompt: str = SYSTEM_PROMPT):
        self.client = client or get_ollama_client()
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt
        self._on_tool_call: Optional[Callable] = None
        self._on_tool_result: Optional[Callable] = None
        self._on_thinking: Optional[Callable] = None

    def on_tool_call(self, callback: Callable) -> None:
        """Register callback for tool call events: callback(tool_name, args)."""
        self._on_tool_call = callback

    def on_tool_result(self, callback: Callable) -> None:
        """Register callback for tool result events: callback(tool_name, result)."""
        self._on_tool_result = callback

    def on_thinking(self, callback: Callable) -> None:
        """Register callback for thinking events: callback(iteration, total)."""
        self._on_thinking = callback

    async def execute(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        extra_context: str = "",
    ) -> Dict[str, Any]:
        """
        Execute the full agentic loop.

        Args:
            user_message: The user's input
            conversation_history: Previous messages in the conversation
            extra_context: Additional context to inject (e.g., matched rules)

        Returns:
            {
                "content": "Final response text",
                "tool_calls_made": [...],
                "iterations": int,
                "duration_ms": int,
            }
        """
        start = time.monotonic()
        tools = get_all_tools()
        tool_calls_made = []

        # Build messages
        messages = [{"role": "system", "content": self.system_prompt}]

        if extra_context:
            messages.append({
                "role": "system",
                "content": f"Relevant traditional rules:\n{extra_context}"
            })

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        # Agentic loop
        for iteration in range(self.max_iterations):
            if self._on_thinking:
                self._on_thinking(iteration + 1, self.max_iterations)

            # Call LLM
            response = await self.client.chat(messages=messages, tools=tools if tools else None)

            # Check for tool calls
            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    tool_args = fn.get("arguments", {})

                    if self._on_tool_call:
                        self._on_tool_call(tool_name, tool_args)

                    # Execute tool
                    result = await self._execute_tool(tool_name, tool_args)
                    tool_calls_made.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result_summary": self._summarize_result(result),
                    })

                    if self._on_tool_result:
                        self._on_tool_result(tool_name, result)

                    # Add assistant message with tool call
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": response["tool_calls"],
                    })

                    # Add tool result
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result, default=str),
                    })

                continue  # Loop back for next LLM response

            # No tool calls — final response
            duration_ms = int((time.monotonic() - start) * 1000)
            return {
                "content": response.get("content", ""),
                "tool_calls_made": tool_calls_made,
                "iterations": iteration + 1,
                "duration_ms": duration_ms,
            }

        # Max iterations reached
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "content": "I've reached the maximum number of tool calls. Here's what I found so far based on the tools I've used.",
            "tool_calls_made": tool_calls_made,
            "iterations": self.max_iterations,
            "duration_ms": duration_ms,
        }

    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a registered tool."""
        handler = _tool_handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}", "available_tools": list(_tool_handlers.keys())[:20]}

        try:
            result = handler(tool_name, args)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return {"error": str(e), "tool": tool_name}

    @staticmethod
    def _summarize_result(result: Any) -> str:
        """Create a brief summary of a tool result for tracking."""
        if isinstance(result, dict):
            if "error" in result:
                return f"Error: {result['error']}"
            keys = list(result.keys())[:5]
            return f"Keys: {', '.join(keys)}"
        return str(result)[:100]


# ─── Memory Tools (LLM-callable) ─────────────────────────────────────────────

def _memory_dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
    """Dispatch memory-related tool calls."""
    from thia_lite.db import get_db
    db = get_db()

    if tool_name == "remember_fact":
        key = args.get("key", "")
        value = args.get("value", "")
        category = args.get("category", "general")
        db.kv_set("memory", key, {
            "value": value,
            "category": category,
        })
        return {"status": "saved", "key": key}

    elif tool_name == "recall_fact":
        key = args.get("key", "")
        data = db.kv_get("memory", key)
        if data and isinstance(data, dict):
            return {"key": key, "value": data.get("value"), "category": data.get("category")}
        return {"key": key, "value": None, "message": "Not found"}

    elif tool_name == "search_memories":
        query = args.get("query", "")
        # Simple search across stored memories
        results = []
        # Search entities
        for entity_type in ["planet", "sign", "house", "aspect", "date"]:
            for term in query.lower().split():
                key = f"{entity_type}:{term}"
                data = db.kv_get("entities", key)
                if data and isinstance(data, dict):
                    results.append({
                        "type": entity_type,
                        "value": data.get("value", term),
                        "context": data.get("last_context", "")[:100],
                        "mentions": data.get("mentions", 0),
                    })
        return {"query": query, "results": results[:10]}

    elif tool_name == "save_birth_data":
        db.kv_set("user_data", "birth_info", {
            "date": args.get("date", ""),
            "time": args.get("time", ""),
            "location": args.get("location", ""),
            "latitude": args.get("latitude"),
            "longitude": args.get("longitude"),
            "timezone": args.get("timezone", ""),
            "name": args.get("name", "User"),
        })
        return {"status": "saved", "birth_data": args}

    elif tool_name == "get_birth_data":
        data = db.kv_get("user_data", "birth_info")
        if data:
            return data
        return {"message": "No birth data saved. Ask the user for their birth date, time, and location."}

    elif tool_name == "astrology_rules_rag_search":
        query = args.get("query", "")
        max_results = args.get("max_results", 5)
        try:
            from thia_lite.rules import search_rules
            matches = search_rules(query, max_results=max_results)
            return {
                "query": query,
                "results": [
                    {
                        "source": r.get("source", ""),
                        "category": r.get("category", ""),
                        "text": r.get("text", ""),
                    }
                    for r in matches
                ],
                "total": len(matches),
            }
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown memory tool: {tool_name}"}


def register_memory_tools():
    """Register all memory-related tools."""

    register_tool(
        "remember_fact",
        "Save a fact to persistent memory. Use this to remember important information about the user, their chart, or anything relevant for future conversations.",
        {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short identifier for the fact (e.g., 'user_sun_sign', 'user_location')"},
                "value": {"type": "string", "description": "The fact to remember"},
                "category": {"type": "string", "description": "Category: general, astrology, preference, personal"},
            },
            "required": ["key", "value"],
        },
        _memory_dispatch,
    )

    register_tool(
        "recall_fact",
        "Recall a previously saved fact from memory.",
        {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The key of the fact to recall"},
            },
            "required": ["key"],
        },
        _memory_dispatch,
    )

    register_tool(
        "search_memories",
        "Search through saved memories and entities for relevant information.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (planets, signs, topics)"},
            },
            "required": ["query"],
        },
        _memory_dispatch,
    )

    register_tool(
        "save_birth_data",
        "Save a person's birth data (date, time, location) for chart calculations.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person's name"},
                "date": {"type": "string", "description": "Birth date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Birth time (HH:MM)"},
                "location": {"type": "string", "description": "Birth location (city, country)"},
                "latitude": {"type": "number", "description": "Latitude"},
                "longitude": {"type": "number", "description": "Longitude"},
                "timezone": {"type": "string", "description": "Timezone (e.g., America/New_York)"},
            },
            "required": ["date"],
        },
        _memory_dispatch,
    )

    register_tool(
        "get_birth_data",
        "Retrieve previously saved birth data for chart calculations.",
        {
            "type": "object",
            "properties": {},
        },
        _memory_dispatch,
    )

    register_tool(
        "astrology_rules_rag_search",
        "Search the traditional astrology rules database (William Lilly and Ptolemy) for rules relevant to a topic. Use this when interpreting charts or answering questions about traditional astrology.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g., 'Saturn in 7th house marriage', 'Moon void of course')"},
                "max_results": {"type": "integer", "description": "Maximum number of rules to return (default: 5)"},
            },
            "required": ["query"],
        },
        _memory_dispatch,
    )
