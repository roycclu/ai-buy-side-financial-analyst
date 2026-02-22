"""Agent 2 — Analyst Agent: financial data extractor with adaptive thinking."""

import sys

from config import MAX_AGENT_TURNS, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR
from llm import create_adapter
from tools import AGENT2_TOOL_DEFINITIONS, AGENT2_FUNCTIONS, execute_tool
from utils.prompts import AGENT2_SYSTEM_PROMPT, build_agent2_message

# Trim history when total content exceeds this (leaves headroom for system prompt + thinking)
_MAX_HISTORY_CHARS = 400_000  # ~100k tokens


def _estimate_chars(messages: list) -> int:
    """Rough character count across all message content."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += len(str(block.get("content", ""))) + len(str(block.get("text", "")))
                else:
                    for attr in ("text", "content", "input"):
                        val = getattr(block, attr, None)
                        if val:
                            total += len(str(val))
    return total


def _trim_tool_results(messages: list) -> list:
    """Replace old tool-result content with a placeholder to stay within context limit.

    Handles both message formats:
    - Anthropic: role=user, content=[{type: tool_result, ...}]
    - Ollama:    role=tool, content=<str>

    The two most-recent messages are always kept intact.
    """
    if _estimate_chars(messages) <= _MAX_HISTORY_CHARS:
        return messages

    PLACEHOLDER = "[content truncated from history to stay within context limit — already processed]"
    trimmed = []
    for i, msg in enumerate(messages):
        is_recent = i >= len(messages) - 2
        if is_recent:
            trimmed.append(msg)
            continue

        role = msg.get("role")
        content = msg.get("content")

        # Anthropic format: role=user with a list of tool_result blocks
        if role == "user" and isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    if len(str(block.get("content", ""))) > 300:
                        new_blocks.append({**block, "content": PLACEHOLDER})
                    else:
                        new_blocks.append(block)
                else:
                    new_blocks.append(block)
            trimmed.append({**msg, "content": new_blocks})

        # Ollama format: role=tool with a plain string content
        elif role == "tool" and isinstance(content, str) and len(content) > 300:
            trimmed.append({**msg, "content": PLACEHOLDER})

        else:
            trimmed.append(msg)

    return trimmed


class AnalystAgent:
    """Reads local filings and extracts structured financial metrics.

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
    """

    def __init__(self, companies: list[dict]):
        self.companies = companies
        self.adapter = create_adapter(thinking=True, thinking_budget=5000)

    def run(self) -> str:
        """Execute the analyst agent loop and return the final summary."""
        print("\n[Agent 2 — Analyst] Extracting financial metrics...", file=sys.stderr)
        print(f"  Companies: {[c['ticker'] for c in self.companies]}", file=sys.stderr)

        user_message = build_agent2_message(
            self.companies, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR
        )
        messages = [{"role": "user", "content": user_message}]

        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling LLM...", file=sys.stderr)
            messages = _trim_tool_results(messages)

            response = self.adapter.chat(messages, AGENT2_SYSTEM_PROMPT, AGENT2_TOOL_DEFINITIONS)

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                results = []
                for tc in response.tool_calls:
                    print(f"  Tool: {tc.name}({tc.input})", file=sys.stderr)
                    results.append(execute_tool(tc.name, tc.input, AGENT2_FUNCTIONS))
                messages.append(self.adapter.make_assistant_message(response))
                messages.extend(self.adapter.make_tool_results_messages(response.tool_calls, results))

            elif response.stop_reason == "end_turn":
                print(f"[Agent 2] Done. ({len(response.text)} chars)", file=sys.stderr)
                return response.text

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return response.text

        print(f"[Agent 2] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        return response.text if response else ""
