"""LLM factory functions — one per framework, respects config.LLM_PROVIDER.

Each factory reads the active LLM_PROVIDER and returns a framework-native
LLM object configured with the correct model and API credentials.
"""

import config


def get_crewai_llm():
    """Return a CrewAI-compatible LLM instance.

    CrewAI's LLM class accepts LiteLLM-style model strings:
      anthropic/<model>  |  <openai-model>  |  ollama/<model>
    """
    from crewai import LLM

    provider = config.LLM_PROVIDER
    if provider == "anthropic":
        return LLM(model=f"anthropic/{config.ANTHROPIC_MODEL}")
    elif provider == "openai":
        return LLM(
            model=config.OPENAI_MODEL,
            base_url=config.OPENAI_BASE_URL,
            api_key=config.OPENAI_API_KEY or "openai",
        )
    else:  # llama / local
        return LLM(
            model=f"ollama/{config.LLAMA_MODEL}",
            base_url=config.LLAMA_BASE_URL,
        )


def get_llamaindex_llm():
    """Return a LlamaIndex-compatible LLM instance."""
    provider = config.LLM_PROVIDER
    if provider == "anthropic":
        from llama_index.llms.anthropic import Anthropic
        return Anthropic(model=config.ANTHROPIC_MODEL)
    elif provider == "openai":
        from llama_index.llms.openai import OpenAI
        return OpenAI(model=config.OPENAI_MODEL, api_base=config.OPENAI_BASE_URL)
    else:  # llama / local
        from llama_index.llms.openai import OpenAI
        return OpenAI(
            model=config.LLAMA_MODEL,
            api_base=config.LLAMA_BASE_URL,
            api_key="ollama",
        )


def get_langchain_llm():
    """Return a LangChain-compatible chat model instance."""
    provider = config.LLM_PROVIDER
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=config.ANTHROPIC_MODEL)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.OPENAI_MODEL,
            base_url=config.OPENAI_BASE_URL,
            api_key=config.OPENAI_API_KEY or "openai",
        )
    else:  # llama / local
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.LLAMA_MODEL,
            base_url=config.LLAMA_BASE_URL,
            api_key="ollama",
        )
