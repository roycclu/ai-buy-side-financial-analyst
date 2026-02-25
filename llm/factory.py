"""Factory that returns the correct LLM adapter based on LLM_PROVIDER config."""

import config
from .base import BaseLLMAdapter
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter
from .llama_adapter import LlamaAdapter


def create_adapter(thinking: bool = False, thinking_budget: int = 8000) -> BaseLLMAdapter:
    """Return a configured LLM adapter.

    Provider is selected by the LLM_PROVIDER environment variable (or config.py):
      "anthropic"  — Anthropic Claude API          (supports extended thinking)
      "openai"     — OpenAI or Gemini cloud APIs    (thinking silently ignored)
      "llama"      — Local Llama-compatible server  (thinking silently ignored)
                     port set via LLAMA_PORT=17777 (local-llm-server)
                                or LLAMA_PORT=11434 (Ollama)

    Args:
        thinking: Request extended thinking (Anthropic only).
        thinking_budget: Token budget for thinking (Anthropic only).
    """
    provider = config.LLM_PROVIDER

    if provider == "openai":
        return OpenAIAdapter(
            model=config.OPENAI_MODEL,
            base_url=config.OPENAI_BASE_URL,
            api_key=config.OPENAI_API_KEY,
            max_tokens=config.MAX_TOKENS,
        )

    if provider == "llama":
        return LlamaAdapter()

    if provider == "anthropic":
        return AnthropicAdapter(thinking=thinking, thinking_budget=thinking_budget)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Valid options: 'anthropic', 'openai', 'llama'."
    )
