"""Normalized LLM interface shared by all adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    stop_reason: str          # "tool_use" | "end_turn" | "other"
    text: str
    tool_calls: list[ToolCall]
    _raw: Any = field(repr=False, default=None)


class BaseLLMAdapter(ABC):
    """Common interface for all LLM provider adapters."""

    @abstractmethod
    def chat(
        self,
        messages: list,
        system: str,
        tools: list,
        thinking: bool = False,
    ) -> LLMResponse:
        """Send a chat request and return a normalized LLMResponse."""

    @abstractmethod
    def make_assistant_message(self, response: LLMResponse) -> dict:
        """Build the assistant message dict to append to history."""

    @abstractmethod
    def make_tool_results_messages(
        self, tool_calls: list[ToolCall], results: list[str]
    ) -> list[dict]:
        """Build the tool-result message(s) to extend history with."""
