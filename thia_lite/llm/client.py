"""
Thia-Lite Universal LLM Client
========================
Wraps multiple LLM providers for unified chat completions
with native tool/function calling support.

Providers: ollama, openai, anthropic, minimax, glm, qwen, moonshot, openrouter
"""

import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


_client: Optional['LLMClient'] = None


# ─── Tool Schema Helpers ──────────────────────────────────────────────────────

def make_ollama_tool(name: str, description: str,
                     parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Create an OpenAI/Ollama-compatible tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        }
    }


def make_anthropic_tool(name: str, description: str,
                        parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Create an Anthropic-compatible tool definition."""
    return {
        "name": name,
        "description": description,
        "input_schema": parameters,
    }

def convert_messages_for_anthropic(messages: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    """Extract system prompt and format messages for Anthropic."""
    system_prompt = ""
    anthropic_msgs = []
    
    for m in messages:
        if m["role"] == "system":
            system_prompt += m["content"] + "\n"
        else:
            anthropic_msgs.append(m)
            
    return system_prompt.strip(), anthropic_msgs

# ─── LLM Client ────────────────────────────────────────────────────────────

class LLMClient:
    """Client for unified chat/completions API with tool calling."""

    def __init__(self, provider: str = "ollama", config: Any = None, api_key: str = ""):
        self.provider = provider
        self.config = config
        self.api_key = api_key
        self.timeout = getattr(config, 'timeout', 120) if config else 120
        self.temperature = getattr(config, 'temperature', 0.3) if config else 0.3
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def is_healthy(self) -> bool:
        """Check if the configured LLM provider is reachable."""
        if self.provider == "ollama":
            host = getattr(self.config, 'host', 'http://localhost:11434').rstrip('/')
            try:
                resp = await self._client.get(f"{host}/api/tags", timeout=5)
                return resp.status_code == 200
            except:
                return False
        # For remote providers, we just check internet connectivity or trust the API keys
        return True

    async def is_model_available(self) -> bool:
        """Check if the configured model is available locally (for Ollama)."""
        if self.provider != "ollama":
            return True
        
        host = getattr(self.config, 'host', 'http://localhost:11434').rstrip('/')
        model = getattr(self.config, 'model', 'qwen3.5:4b')
        try:
            resp = await self._client.get(f"{host}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return model in models or any(m.startswith(f"{model}:") for m in models)
        except:
            pass
        return False

    # ─── Chat Completion ──────────────────────────────────────────────────

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send a chat completion request routing to correct provider."""
        temp = temperature if temperature is not None else self.temperature
        start_time = time.monotonic()

        try:
            if self.provider == "ollama":
                return await self._chat_ollama(messages, tools, temp)
            elif self.provider in ["openai", "glm", "qwen", "moonshot", "openrouter", "minimax"]:
                return await self._chat_openai_compatible(self.provider, messages, tools, temp)
            elif self.provider in ["anthropic"]:
                return await self._chat_anthropic_compatible(self.provider, messages, tools, temp)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        except httpx.TimeoutException:
            logger.error(f"{self.provider} request timed out after {self.timeout}s")
            return {
                "role": "assistant",
                "content": "I apologize, but the request timed out. Please try again.",
                "tool_calls": None,
                "done": True,
            }
        except Exception as e:
            logger.error(f"{self.provider} chat error: {e}")
            return {
                "role": "assistant",
                "content": f"Error communicating with {self.provider}: {e}",
                "tool_calls": None,
                "done": True,
            }

    async def _chat_ollama(self, messages, tools, temperature):
        host = getattr(self.config, 'host', 'http://localhost:11434').rstrip('/')
        model = getattr(self.config, 'model', 'qwen3.5:4b')
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 4096},
        }
        if tools:
            # Ollama uses OpenAI format for tools
            payload["tools"] = tools

        resp = await self._client.post(f"{host}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message", {})
        
        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
            "tool_calls": message.get("tool_calls"),
            "done": data.get("done", True),
        }

    async def _chat_openai_compatible(self, provider, messages, tools, temperature):
        base_urls = {
            "openai": "https://api.openai.com/v1",
            "glm": "https://open.bigmodel.cn/api/paas/v4",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "moonshot": "https://api.moonshot.cn/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "minimax": "https://api.minimax.chat/v1",
        }
        
        default_models = {
            "openai": "gpt-4o-mini",
            "glm": "glm-4",
            "qwen": "qwen-turbo",
            "moonshot": "moonshot-v1-8k",
            "openrouter": "anthropic/claude-3-haiku",
            "minimax": "minimax-text-01",
        }
        
        api_key = self.api_key
        if not api_key:
            # Fallback to config file if not passed dynamically (e.g. CLI usage)
            api_keys = {
                "openai": getattr(self.config, 'openai_api_key', ''),
                "glm": getattr(self.config, 'glm_api_key', ''),
                "qwen": getattr(self.config, 'qwen_api_key', ''),
                "moonshot": getattr(self.config, 'moonshot_api_key', ''),
                "openrouter": getattr(self.config, 'openrouter_api_key', ''),
                "minimax": getattr(self.config, 'minimax_api_key', ''),
            }
            api_key = api_keys.get(provider, '')

        if not api_key:
            return {"role": "assistant", "content": f"Missing API key for {provider}", "tool_calls": None, "done": True}

        base_url = base_urls[provider]
        model = getattr(self.config, 'model', None)
        if not model or model.startswith('qwen3.5:'):
            model = default_models[provider]

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/SubLunarTech/thia-lite"
            headers["X-Title"] = "Thia-Lite"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        resp = await self._client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        message = data.get("choices", [{}])[0].get("message", {})
        
        # Standardize tool calls format to match Ollama's expected output for the executor
        tool_calls = message.get("tool_calls")
        standardized_tools = None
        if tool_calls:
            standardized_tools = []
            for tc in tool_calls:
                args = tc.get("function", {}).get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}
                standardized_tools.append({
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": args
                    }
                })

        return {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
            "tool_calls": standardized_tools,
            "done": True,
        }

    async def _chat_anthropic_compatible(self, provider, messages, tools, temperature):
        base_urls = {
            "anthropic": "https://api.anthropic.com/v1",
            "minimax": "https://api.minimax.io/anthropic",
        }
        
        default_models = {
            "anthropic": "claude-3-5-sonnet-20240620",
            "minimax": "MiniMax-M2.5",
        }
        
        api_keys = {
            "anthropic": getattr(self.config, 'anthropic_api_key', ''),
            "minimax": getattr(self.config, 'minimax_api_key', ''),
        }
        
        base_url = base_urls[provider]
        model = getattr(self.config, 'model', None)
        if model in ("qwen3.5:9b", "qwen3.5:4b") or not model:
            model = default_models[provider]
            
        api_key = api_keys[provider]
        if not api_key:
            return {"role": "assistant", "content": f"Missing API key for {provider}", "tool_calls": None, "done": True}

        system_prompt, anthropic_msgs = convert_messages_for_anthropic(messages)

        headers = {
            "Content-Type": "application/json"
        }
        if provider == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else: # Minimax
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": anthropic_msgs,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        if tools:
            # Convert OpenAI format tools to Anthropic format
            anthropic_tools = [
                make_anthropic_tool(t["function"]["name"], t["function"]["description"], t["function"]["parameters"]) 
                for t in tools if "function" in t
            ]
            payload["tools"] = anthropic_tools

        resp = await self._client.post(f"{base_url}/messages", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        content_blocks = data.get("content", [])
        text_content = ""
        tool_calls = None
        
        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "function": {
                        "name": block.get("name"),
                        "arguments": block.get("input", {})
                    }
                })

        return {
            "role": "assistant",
            "content": text_content.strip(),
            "tool_calls": tool_calls,
            "done": True,
        }

    # ─── Stream and Embeddings ──────────────────────────────────────────

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """Stream a chat response token-by-token (No tool calling)"""
        if self.provider != "ollama":
            # Just return full chat for non-ollama to keep it simple for now
            resp = await self.chat(messages, temperature=temperature)
            yield resp["content"]
            return
            
        host = getattr(self.config, 'host', 'http://localhost:11434').rstrip('/')
        model = getattr(self.config, 'model', 'qwen3.5:4b')
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature or self.temperature},
        }

        async with self._client.stream("POST", f"{host}/api/chat", json=payload) as resp:
            async for line in resp.aiter_lines():
                if not line.strip(): continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content: yield content
                    if chunk.get("done", False): break
                except: continue

    async def embed(self, text: str) -> Optional[List[float]]:
        """Generate embeddings using Ollama regardless of configured chat provider."""
        host = getattr(self.config, 'host', 'http://localhost:11434').rstrip('/')
        model = getattr(self.config, 'model', 'qwen3.5:4b') # Could use tinyllama or all-minilm
        try:
            resp = await self._client.post(
                f"{host}/api/embed",
                json={"model": model, "input": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            return embeddings[0] if embeddings else None
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            return None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        results = []
        for text in texts:
            results.append(await self.embed(text))
        return results


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_llm_client(provider: Optional[str] = None, config: Optional[Any] = None, api_key: str = "", model: Optional[str] = None, temperature: Optional[float] = None) -> LLMClient:
    """Get or create the global LLM client, or create a temporary one if kwargs overlap."""
    global _client
    if provider is not None:
        from thia_lite.config import get_settings
        cfg = get_settings().llm
        c = LLMClient(provider=provider, config=cfg, api_key=api_key)
        if model:
            c.config = type('Config', (), {
                'model': model,
                'host': cfg.host,
                'timeout': cfg.timeout,
                'temperature': temperature if temperature is not None else cfg.temperature,
                'openai_api_key': cfg.openai_api_key,
                'anthropic_api_key': cfg.anthropic_api_key,
                'minimax_api_key': cfg.minimax_api_key,
                'glm_api_key': cfg.glm_api_key,
                'qwen_api_key': cfg.qwen_api_key,
                'moonshot_api_key': cfg.moonshot_api_key,
                'openrouter_api_key': cfg.openrouter_api_key,
            })()
        if temperature is not None: c.temperature = temperature
        return c

    if _client is None:
        from thia_lite.config import get_settings
        cfg = get_settings().llm
        _client = LLMClient(provider=cfg.provider, config=cfg)
    return _client
