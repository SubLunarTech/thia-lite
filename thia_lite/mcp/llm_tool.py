"""
Thia-Lite MCP LLM Tool
=======================
Expose LLM chat completion functionality via MCP protocol.
This allows the Electron app to use the CLI's LLM client for all inference.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def llm_chat(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an LLM chat completion request.

    Args:
        tool_name: The tool name (should be 'llm_chat')
        args: Dictionary containing:
            - messages: List of message dicts with 'role' and 'content'
            - temperature: Optional temperature override
            - tools: Optional list of tool definitions for function calling

    Returns:
        Dict with the LLM response
    """
    from thia_lite.llm.client import get_llm_client

    messages = args.get("messages", [])
    temperature = args.get("temperature")
    tools = args.get("tools")

    if not messages:
        return {"error": "No messages provided"}

    # Get LLM client (uses configured provider from settings)
    client = get_llm_client()

    # Convert tools to OpenAI format if provided
    mcp_tools = None
    if tools:
        mcp_tools = []
        for tool in tools:
            if "function" in tool:
                # Already in OpenAI format
                mcp_tools.append(tool)
            else:
                # MCP format, convert to OpenAI
                mcp_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                        "parameters": tool.get("inputSchema", tool.get("parameters", {}))
                    }
                })

    try:
        import asyncio

        async def do_chat():
            result = await client.chat(
                messages=messages,
                tools=mcp_tools,
                temperature=temperature,
            )
            return result

        # Run async function
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # We're in an async context already, use await
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, do_chat()).result()
        else:
            result = asyncio.run(do_chat())

        logger.info(f"LLM chat completed: provider={client.provider}")

        return {
            "role": result.get("role", "assistant"),
            "content": result.get("content", ""),
            "tool_calls": result.get("tool_calls"),
            "done": result.get("done", True),
            "provider": client.provider,
        }

    except Exception as e:
        logger.error(f"LLM chat failed: {e}")
        return {
            "error": str(e),
            "role": "assistant",
            "content": f"LLM Error: {e}",
            "done": True,
        }


def llm_get_models(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Get available models for the current LLM provider.

    Returns:
        Dict with model information
    """
    from thia_lite.llm.client import get_llm_client
    from thia_lite.config import get_settings

    settings = get_settings()
    client = get_llm_client()

    result = {
        "provider": client.provider,
        "model": getattr(client.config, 'model', 'unknown'),
    }

    # For Ollama, list available models
    if client.provider == "ollama":
        import asyncio

        async def check_models():
            healthy = await client.is_healthy()
            if healthy:
                try:
                    import httpx
                    host = getattr(client.config, 'host', 'http://localhost:11434').rstrip('/')
                    async with httpx.AsyncClient(timeout=5) as hc:
                        resp = await hc.get(f"{host}/api/tags")
                        if resp.status_code == 200:
                            data = resp.json()
                            return data.get("models", [])
                except Exception as e:
                    logger.warning(f"Failed to get Ollama models: {e}")
            return []

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                models = pool.submit(asyncio.run, check_models()).result()
        else:
            models = asyncio.run(check_models())

        result["available_models"] = [m.get("name") for m in models]
        result["model_available"] = await client.is_model_available()

    # Cloud providers - just return configured model
    else:
        result["available_models"] = [result["model"]]
        result["model_available"] = True

    return result


def llm_set_provider(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Set the LLM provider and/or model.

    Args:
        provider: The provider name (ollama, openai, anthropic, etc.)
        model: Optional model override
        api_key: Optional API key for cloud providers

    Returns:
        Dict with the new configuration
    """
    from thia_lite.config import save_config
    from thia_lite.llm.client import get_llm_client

    provider = args.get("provider")
    model = args.get("model")
    api_key = args.get("api_key")

    if provider:
        config_updates = {"llm.provider": provider}
        if model:
            config_updates["llm.model"] = model
        if api_key:
            # Save API key for the provider
            api_key_map = {
                "openai": "llm.openai_api_key",
                "anthropic": "llm.anthropic_api_key",
                "openrouter": "llm.openrouter_api_key",
                "glm": "llm.glm_api_key",
                "qwen": "llm.qwen_api_key",
                "moonshot": "llm.moonshot_api_key",
                "minimax": "llm.minimax_api_key",
            }
            if provider in api_key_map:
                config_updates[api_key_map[provider]] = api_key

        try:
            save_config(config_updates)
            # Clear the global client so it gets recreated with new config
            import thia_lite.llm.client as client_module
            client_module._client = None

            return {
                "success": True,
                "provider": provider,
                "model": model or getattr(get_llm_client().config, 'model', 'unknown'),
            }
        except Exception as e:
            return {"error": f"Failed to set provider: {e}"}

    return {"error": "No provider specified"}


# Register the tools
def register_llm_tools():
    """Register LLM-related tools with the tool executor."""
    from thia_lite.llm.tool_executor import register_tool

    register_tool(
        "llm_chat",
        "Execute an LLM chat completion request. Supports both local (Ollama) and cloud providers.",
        {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "description": "Array of message objects with 'role' and 'content' fields",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                            "content": {"type": "string"}
                        },
                        "required": ["role", "content"]
                    }
                },
                "temperature": {
                    "type": "number",
                    "description": "Optional temperature override (0.0 - 1.0)"
                },
                "tools": {
                    "type": "array",
                    "description": "Optional list of tool definitions for function calling"
                }
            },
            "required": ["messages"]
        },
        llm_chat
    )

    register_tool(
        "llm_get_models",
        "Get available models for the current LLM provider",
        {
            "type": "object",
            "properties": {},
            "required": []
        },
        llm_get_models
    )

    register_tool(
        "llm_set_provider",
        "Set the LLM provider and/or model",
        {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["ollama", "openai", "anthropic", "openrouter", "glm", "qwen", "moonshot", "minimax"],
                    "description": "The LLM provider to use"
                },
                "model": {
                    "type": "string",
                    "description": "Optional model override"
                },
                "api_key": {
                    "type": "string",
                    "description": "Optional API key for cloud providers"
                }
            },
            "required": ["provider"]
        },
        llm_set_provider
    )

    logger.info("LLM tools registered with MCP")
