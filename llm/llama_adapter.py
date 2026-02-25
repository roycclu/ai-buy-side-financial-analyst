"""Llama / local server adapter.

Routes to a locally-running Llama-compatible inference server.  Both common
local backends speak the OpenAI Chat Completions protocol, so this adapter
delegates the wire format to OpenAIAdapter while exposing a distinct provider
identity and its own config section.

Supported backends:
  - local-llm-server  (default port 17777)   set LLAMA_PORT=17777
  - Ollama            (default port 11434)   set LLAMA_PORT=11434
  - vLLM, LM Studio, or any OpenAI-compatible local server

Config (all optional — defaults shown):
  LLAMA_PORT=17777          # ← one-liner to switch between backends
  LLAMA_HOST=127.0.0.1
  LLAMA_MODEL=llama3.2:3b
  LLAMA_BASE_URL=http://127.0.0.1:17777/v1  # override full URL if needed
"""

import config
from .base import BaseLLMAdapter, LLMResponse, ToolCall
from .openai_adapter import OpenAIAdapter


class LlamaAdapter(BaseLLMAdapter):
    """Calls a local Llama-compatible server using the OpenAI-compatible protocol.

    Configure the target port with LLAMA_PORT in your .env:
      LLAMA_PORT=17777   →  local-llm-server
      LLAMA_PORT=11434   →  Ollama
    """

    def __init__(self):
        self._delegate = OpenAIAdapter(
            model=config.LLAMA_MODEL,
            base_url=config.LLAMA_BASE_URL,
            api_key="local",           # local servers don't need a real key
            max_tokens=config.MAX_TOKENS,
        )

    def chat(
        self,
        messages: list,
        system: str,
        tools: list,
        thinking: bool = False,
    ) -> LLMResponse:
        # Extended thinking is an Anthropic-only feature; ignored here
        return self._delegate.chat(messages, system, tools, thinking=False)

    def make_assistant_message(self, response: LLMResponse) -> dict:
        return self._delegate.make_assistant_message(response)

    def make_tool_results_messages(
        self, tool_calls: list[ToolCall], results: list[str]
    ) -> list[dict]:
        return self._delegate.make_tool_results_messages(tool_calls, results)
