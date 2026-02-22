"""Agent 1 — Research Agent: SEC EDGAR filing fetcher with cache-first logic."""

import sys

from config import MAX_AGENT_TURNS, FINANCIAL_FILES_DIR
from llm import create_adapter
from tools import AGENT1_TOOL_DEFINITIONS, AGENT1_FUNCTIONS, execute_tool
from utils.prompts import AGENT1_SYSTEM_PROMPT, build_agent1_message


class ResearchAgent:
    """Fetches SEC EDGAR filings for a list of companies, with cache-first logic.

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
    """

    def __init__(self, companies: list[dict]):
        self.companies = companies
        self.adapter = create_adapter(thinking=False)

    def run(self) -> str:
        """Execute the research agent loop and return the final summary."""
        print("\n[Agent 1 — Research] Starting SEC EDGAR filing collection...", file=sys.stderr)
        print(f"  Companies: {[c['ticker'] for c in self.companies]}", file=sys.stderr)

        user_message = build_agent1_message(self.companies, FINANCIAL_FILES_DIR)
        messages = [{"role": "user", "content": user_message}]

        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling LLM...", file=sys.stderr)

            response = self.adapter.chat(messages, AGENT1_SYSTEM_PROMPT, AGENT1_TOOL_DEFINITIONS)

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                results = []
                for tc in response.tool_calls:
                    print(f"  Tool: {tc.name}({tc.input})", file=sys.stderr)
                    results.append(execute_tool(tc.name, tc.input, AGENT1_FUNCTIONS))
                messages.append(self.adapter.make_assistant_message(response))
                messages.extend(self.adapter.make_tool_results_messages(response.tool_calls, results))

            elif response.stop_reason == "end_turn":
                print(f"[Agent 1] Done. ({len(response.text)} chars)", file=sys.stderr)
                return response.text

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return response.text

        print(f"[Agent 1] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        return response.text if response else ""
