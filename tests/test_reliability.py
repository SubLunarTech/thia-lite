import pytest
import asyncio
from typing import Dict, Any
from thia_lite.llm.client import get_llm_client
from thia_lite.config import get_settings

@pytest.mark.asyncio
async def test_llm_client_health():
    """Test that the LLM client correctly reports health."""
    client = get_llm_client()
    # If Ollama is not running, this might be false, which is expected
    # We're testing that the method works and doesn't crash
    try:
        is_healthy = await client.is_healthy()
        assert isinstance(is_healthy, bool)
    except Exception as e:
        pytest.fail(f"LLMClient.is_healthy crashed: {e}")

@pytest.mark.asyncio
async def test_llm_model_available():
    """Test that the model availability check works."""
    client = get_llm_client()
    try:
        available = await client.is_model_available()
        assert isinstance(available, bool)
    except Exception as e:
        pytest.fail(f"LLMClient.is_model_available crashed: {e}")

def test_config_dirs():
    """Test that ensures directory structure is initialized."""
    from thia_lite.config import _ensure_dirs
    _ensure_dirs()
    settings = get_settings()
    assert settings.config_dir.exists()
    assert (settings.config_dir / "logs").exists()
    assert (settings.config_dir / "logs" / "thia.log").exists()

def test_registry():
    """Test that tools are properly registered."""
    from thia_lite.llm.tool_executor import get_tool_names, register_memory_tools
    register_memory_tools()
    names = get_tool_names()
    assert "remember_fact" in names
    assert "search_memories" in names
    assert "astrology_rules_rag_search" in names
