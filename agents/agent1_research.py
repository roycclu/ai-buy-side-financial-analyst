"""Agent 1 — Research Agent: SEC EDGAR filing fetcher with cache-first logic."""

import sys

import anthropic

from config import MODEL, MAX_TOKENS, MAX_AGENT_TURNS, FINANCIAL_FILES_DIR
from tools import AGENT1_TOOL_DEFINITIONS, AGENT1_FUNCTIONS, execute_tool
from utils.prompts import AGENT1_SYSTEM_PROMPT, build_agent1_message


def _extract_text(content_blocks) -> str:
    return "\n".join(b.text for b in content_blocks if hasattr(b, "text"))


class ResearchAgent:
    """Fetches SEC EDGAR filings for a list of companies, with cache-first logic.

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
    """

    def __init__(self, companies: list[dict]):
        self.companies = companies
        self.client = anthropic.Anthropic()

    def run(self) -> str:
        """Execute the research agent loop and return the final summary."""
        print("\n[Agent 1 — Research] Starting SEC EDGAR filing collection...", file=sys.stderr)
        print(f"  Companies: {[c['ticker'] for c in self.companies]}", file=sys.stderr)

        user_message = build_agent1_message(self.companies, FINANCIAL_FILES_DIR)
        messages = [{"role": "user", "content": user_message}]

        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling Claude...", file=sys.stderr)

            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=AGENT1_SYSTEM_PROMPT,
                tools=AGENT1_TOOL_DEFINITIONS,
                messages=messages,
            )

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"  Tool: {block.name}({block.input})", file=sys.stderr)
                        result = execute_tool(block.name, block.input, AGENT1_FUNCTIONS)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                summary = _extract_text(response.content)
                print(f"[Agent 1] Done. ({len(summary)} chars)", file=sys.stderr)
                return summary

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return _extract_text(response.content)

        print(f"[Agent 1] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        return _extract_text(response.content) if response else ""
