"""Agent 2 — Analyst Agent: financial data extractor with adaptive thinking."""

import sys

import anthropic

from config import MODEL, MAX_TOKENS, MAX_AGENT_TURNS, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR
from tools import AGENT2_TOOL_DEFINITIONS, AGENT2_FUNCTIONS, execute_tool
from utils.prompts import AGENT2_SYSTEM_PROMPT, build_agent2_message

# Trim history when total content exceeds this (leaves headroom for system prompt + thinking)
_MAX_HISTORY_CHARS = 400_000  # ~100k tokens


def _extract_text(content_blocks) -> str:
    return "\n".join(b.text for b in content_blocks if hasattr(b, "text"))


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
    """Replace old tool_result content with a placeholder to stay within the context limit.

    The two most-recent messages (the last assistant turn + its tool results) are always
    kept intact so the model retains full context for the current step.
    """
    if _estimate_chars(messages) <= _MAX_HISTORY_CHARS:
        return messages

    trimmed = []
    for i, msg in enumerate(messages):
        is_recent = i >= len(messages) - 2
        if (
            not is_recent
            and msg.get("role") == "user"
            and isinstance(msg.get("content"), list)
        ):
            new_blocks = []
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if len(str(content)) > 300:
                        new_blocks.append({
                            **block,
                            "content": "[content truncated from history to stay within context limit — already processed]",
                        })
                    else:
                        new_blocks.append(block)
                else:
                    new_blocks.append(block)
            trimmed.append({**msg, "content": new_blocks})
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
        self.client = anthropic.Anthropic()

    def run(self) -> str:
        """Execute the analyst agent loop and return the final summary."""
        print("\n[Agent 2 — Analyst] Extracting financial metrics...", file=sys.stderr)
        print(f"  Companies: {[c['ticker'] for c in self.companies]}", file=sys.stderr)

        user_message = build_agent2_message(
            self.companies, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR
        )
        messages = [{"role": "user", "content": user_message}]

        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling Claude...", file=sys.stderr)
            messages = _trim_tool_results(messages)

            response = self.client.beta.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "enabled", "budget_tokens": 5000},
                system=AGENT2_SYSTEM_PROMPT,
                tools=AGENT2_TOOL_DEFINITIONS,
                messages=messages,
                betas=["interleaved-thinking-2025-05-14"],
            )

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"  Tool: {block.name}({block.input})", file=sys.stderr)
                        result = execute_tool(block.name, block.input, AGENT2_FUNCTIONS)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                summary = _extract_text(response.content)
                print(f"[Agent 2] Done. ({len(summary)} chars)", file=sys.stderr)
                return summary

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return _extract_text(response.content)

        print(f"[Agent 2] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        return _extract_text(response.content) if response else ""
