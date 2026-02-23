"""Factory that returns the correct LLM adapter based on LLM_PROVIDER config."""

import config
from .base import BaseLLMAdapter
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter


def create_adapter(thinking: bool = False, thinking_budget: int = 8000) -> BaseLLMAdapter:
    """Return a configured LLM adapter.

    Provider is selected by the LLM_PROVIDER environment variable:
      "anthropic"  — Anthropic Claude (supports extended thinking)
      "openai"     — OpenAI or any OpenAI-compatible endpoint
                     (extended thinking is silently ignored)

    Args:
        thinking: Request extended thinking (Anthropic only).
        thinking_budget: Token budget for thinking (Anthropic only).
    """
    if config.LLM_PROVIDER == "openai":
        return OpenAIAdapter(
            model=config.OPENAI_MODEL,
            base_url=config.OPENAI_BASE_URL,
            api_key=config.OPENAI_API_KEY,
        )
    # Default: Anthropic
    return AnthropicAdapter(thinking=thinking, thinking_budget=thinking_budget)
