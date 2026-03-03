"""
Thia-Lite Ollama Client
========================
Wraps Ollama's OpenAI-compatible API for chat completions
with native tool/function calling support.

Targets Qwen3.5-9B for reliable structured output.
"""

import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ─── Tool Schema Helpers ──────────────────────────────────────────────────────

def make_ollama_tool(name: str, description: str,
                     parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Create an Ollama-compatible tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        }
    }


# ─── Ollama Client ────────────────────────────────────────────────────────────

class OllamaClient:
    """Client for Ollama's chat/completions API with tool calling."""

    def __init__(self, host: str = "http://localhost:11434",
                 model: str = "qwen3.5:9b",
                 timeout: int = 120,
                 temperature: float = 0.3):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    # ─── Health ───────────────────────────────────────────────────────────

    async def is_healthy(self) -> bool:
        """Check if Ollama is running and reachable."""
        try:
            resp = await self._client.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    async def is_model_available(self) -> bool:
        """Check if the configured model is pulled."""
        try:
            resp = await self._client.get(f"{self.host}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = resp.json().get("models", [])
            return any(m.get("name", "").startswith(self.model) for m in models)
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """List all available models."""
        try:
            resp = await self._client.get(f"{self.host}/api/tags", timeout=5)
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            pass
        return []

    # ─── Chat Completion ──────────────────────────────────────────────────

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request.

        Returns:
            {
                "role": "assistant",
                "content": "...",
                "tool_calls": [...] or None,
                "done": True,
                "total_duration": ...,
                "eval_count": ...
            }
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,  # Non-streaming for tool calls
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": 4096,
            },
        }

        if tools:
            payload["tools"] = tools

        try:
            resp = await self._client.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            message = data.get("message", {})
            return {
                "role": message.get("role", "assistant"),
                "content": message.get("content", ""),
                "tool_calls": message.get("tool_calls"),
                "done": data.get("done", True),
                "total_duration": data.get("total_duration", 0),
                "eval_count": data.get("eval_count", 0),
            }

        except httpx.TimeoutException:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            return {
                "role": "assistant",
                "content": "I apologize, but the request timed out. Please try again.",
                "tool_calls": None,
                "done": True,
                "total_duration": 0,
                "eval_count": 0,
            }
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            return {
                "role": "assistant",
                "content": f"Error communicating with Ollama: {e}",
                "tool_calls": None,
                "done": True,
                "total_duration": 0,
                "eval_count": 0,
            }

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """Stream a chat response token-by-token (no tool calling in stream mode)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature or self.temperature,
            },
        }

        async with self._client.stream(
            "POST",
            f"{self.host}/api/chat",
            json=payload,
            timeout=self.timeout,
        ) as resp:
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

    # ─── Embeddings ───────────────────────────────────────────────────────

    async def embed(self, text: str) -> Optional[List[float]]:
        """Generate an embedding vector for text using the current model."""
        try:
            resp = await self._client.post(
                f"{self.host}/api/embed",
                json={"model": self.model, "input": text},
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
        """Embed multiple texts."""
        results = []
        for text in texts:
            results.append(await self.embed(text))
        return results


# ─── Factory ──────────────────────────────────────────────────────────────────

_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get or create the global Ollama client."""
    global _client
    if _client is None:
        from thia_lite.config import get_settings
        s = get_settings()
        _client = OllamaClient(
            host=s.ollama.host,
            model=s.ollama.model,
            timeout=s.ollama.timeout,
            temperature=s.ollama.temperature,
        )
    return _client
