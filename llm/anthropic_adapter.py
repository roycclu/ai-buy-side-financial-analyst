"""Anthropic Claude adapter — wraps the Anthropic SDK."""

import anthropic

import config
from .base import BaseLLMAdapter, LLMResponse, ToolCall


class AnthropicAdapter(BaseLLMAdapter):
    """Calls Anthropic claude via messages.create (or beta for thinking)."""

    def __init__(self, thinking: bool = False, thinking_budget: int = 8000):
        self.thinking = thinking
        self.thinking_budget = thinking_budget
        self.client = anthropic.Anthropic()

    def chat(self, messages, system, tools, thinking: bool = False) -> LLMResponse:
        use_thinking = self.thinking or thinking

        if use_thinking:
            raw = self.client.beta.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=config.MAX_TOKENS,
                thinking={"type": "enabled", "budget_tokens": self.thinking_budget},
                system=system,
                tools=tools,
                messages=messages,
                betas=["interleaved-thinking-2025-05-14"],
            )
        else:
            raw = self.client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=config.MAX_TOKENS,
                system=system,
                tools=tools,
                messages=messages,
            )

        text = "\n".join(b.text for b in raw.content if hasattr(b, "text"))
        tool_calls = [
            ToolCall(id=b.id, name=b.name, input=b.input)
            for b in raw.content
            if b.type == "tool_use"
        ]
        stop_reason = raw.stop_reason or "other"
        return LLMResponse(stop_reason=stop_reason, text=text, tool_calls=tool_calls, _raw=raw)

    def make_assistant_message(self, response: LLMResponse) -> dict:
        # Preserve Pydantic block objects — Anthropic SDK accepts them back as-is
        return {"role": "assistant", "content": response._raw.content}

    def make_tool_results_messages(
        self, tool_calls: list[ToolCall], results: list[str]
    ) -> list[dict]:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result,
                    }
                    for tc, result in zip(tool_calls, results)
                ],
            }
        ]
