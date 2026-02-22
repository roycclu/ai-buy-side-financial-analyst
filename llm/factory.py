"""Factory that returns the correct adapter based on LLM_PROVIDER config."""

import config
from .base import BaseLLMAdapter
from .anthropic_adapter import AnthropicAdapter
from .ollama_adapter import OllamaAdapter


def create_adapter(thinking: bool = False, thinking_budget: int = 8000) -> BaseLLMAdapter:
    """Return an LLM adapter configured from environment variables.

    Args:
        thinking: Enable extended thinking (Anthropic only; ignored for Ollama).
        thinking_budget: Token budget for thinking (Anthropic only).
    """
    if config.LLM_PROVIDER == "ollama":
        return OllamaAdapter(model=config.LOCAL_MODEL, base_url=config.OLLAMA_BASE_URL)
    return AnthropicAdapter(thinking=thinking, thinking_budget=thinking_budget)
