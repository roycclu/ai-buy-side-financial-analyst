"""Ollama adapter — uses the OpenAI-compatible endpoint served by Ollama."""

import json

from openai import OpenAI

from .base import BaseLLMAdapter, LLMResponse, ToolCall


def _convert_tools(tools: list) -> list:
    """Convert Anthropic-format tool defs to OpenAI function format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def _finish_to_stop_reason(finish_reason: str, has_tool_calls: bool) -> str:
    if has_tool_calls or finish_reason == "tool_calls":
        return "tool_use"
    if finish_reason == "stop":
        return "end_turn"
    return "other"


class OllamaAdapter(BaseLLMAdapter):
    """Calls a locally-running Ollama instance via its OpenAI-compatible API."""

    def __init__(self, model: str, base_url: str):
        self.model = model
        self.client = OpenAI(base_url=f"{base_url}/v1", api_key="ollama")

    def chat(self, messages, system, tools, thinking: bool = False) -> LLMResponse:
        # Ollama/OpenAI uses a system message rather than a top-level param
        all_messages = [{"role": "system", "content": system}] + messages
        converted_tools = _convert_tools(tools) if tools else None

        raw = self.client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            tools=converted_tools,
        )

        choice = raw.choices[0]
        message = choice.message
        text = message.content or ""

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        input=json.loads(tc.function.arguments),
                    )
                )

        stop_reason = _finish_to_stop_reason(choice.finish_reason or "", bool(tool_calls))
        return LLMResponse(stop_reason=stop_reason, text=text, tool_calls=tool_calls, _raw=raw)

    def make_assistant_message(self, response: LLMResponse) -> dict:
        raw_msg = response._raw.choices[0].message
        msg: dict = {"role": "assistant", "content": raw_msg.content or ""}
        if raw_msg.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in raw_msg.tool_calls
            ]
        return msg

    def make_tool_results_messages(
        self, tool_calls: list[ToolCall], results: list[str]
    ) -> list[dict]:
        # OpenAI/Ollama expects one message per tool result
        return [
            {"role": "tool", "tool_call_id": tc.id, "content": result}
            for tc, result in zip(tool_calls, results)
        ]
