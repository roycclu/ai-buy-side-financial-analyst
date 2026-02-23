"""Agent 3 — Lead Analyst: investment thesis + sector report with adaptive thinking.

Agent 3 reads ONLY the compact summary files produced by Agent 2:
  {TICKER}_facts_latest.json  — structured KPIs (small)
  {TICKER}_brief_latest.md    — human-readable brief (small)
  {TICKER}_quote_bank.json    — top management quotes (small)

It never ingests raw filings wholesale. search_excerpts() is available for targeted
retrieval when a specific citation is needed.
"""

import json
import re
import sys

from config import MAX_AGENT_TURNS, FINANCIAL_DATA_DIR, FINANCIAL_ANALYSES_DIR
from llm import create_adapter
from tools import AGENT3_TOOL_DEFINITIONS, AGENT3_FUNCTIONS, execute_tool
from utils.prompts import AGENT3_SYSTEM_PROMPT, build_agent3_message


def _parse_viz_specs(text: str) -> list[dict]:
    """Extract the JSON viz_specs block from Agent 3's output."""
    try:
        match = re.search(r"```json\s*(\{.*?\"viz_specs\".*?\})\s*```", text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return data.get("viz_specs", [])
    except Exception:
        pass

    try:
        match = re.search(r'\{[^{}]*"viz_specs"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return data.get("viz_specs", [])
    except Exception:
        pass

    return []


class AnalystLead:
    """Writes per-company analyst reports and a sector synthesis report.

    Reads compact summary files (facts JSON + brief MD + quote bank) rather than
    raw filings, so the session context stays small regardless of company count.

    Args:
        project: Project name.
        companies: List of dicts with 'name' and 'ticker' keys.
        research_question: The client's primary research question.
    """

    def __init__(self, project: str, companies: list[dict], research_question: str):
        self.project = project
        self.companies = companies
        self.research_question = research_question
        self.adapter = create_adapter(thinking=True, thinking_budget=8000)

    def run(self) -> dict:
        """Execute the lead analyst loop.

        Returns:
            Dict with 'sector_report' text and 'viz_specs' list.
        """
        print("\n[Agent 3 — Lead Analyst] Writing investment analysis...", file=sys.stderr)
        print(f"  Project: {self.project}", file=sys.stderr)
        print(f"  Research question: {self.research_question}", file=sys.stderr)
        print(f"  Reading compact summaries from: {FINANCIAL_DATA_DIR}", file=sys.stderr)

        user_message = build_agent3_message(
            self.project,
            self.companies,
            self.research_question,
            FINANCIAL_DATA_DIR,
            FINANCIAL_ANALYSES_DIR,
        )
        messages = [{"role": "user", "content": user_message}]

        last_response = None
        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling LLM...", file=sys.stderr)

            response = self.adapter.chat(messages, AGENT3_SYSTEM_PROMPT, AGENT3_TOOL_DEFINITIONS)
            last_response = response

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                results = []
                for tc in response.tool_calls:
                    print(f"  Tool: {tc.name}({list(tc.input.keys())})", file=sys.stderr)
                    results.append(execute_tool(tc.name, tc.input, AGENT3_FUNCTIONS))
                messages.append(self.adapter.make_assistant_message(response))
                messages.extend(self.adapter.make_tool_results_messages(response.tool_calls, results))

            elif response.stop_reason == "end_turn":
                viz_specs = _parse_viz_specs(response.text)
                print(
                    f"[Agent 3] Done. ({len(response.text)} chars, "
                    f"{len(viz_specs)} viz specs)",
                    file=sys.stderr,
                )
                return {"sector_report": response.text, "viz_specs": viz_specs}

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return {"sector_report": response.text, "viz_specs": []}

        print(f"[Agent 3] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        final_text = last_response.text if last_response else ""
        return {"sector_report": final_text, "viz_specs": _parse_viz_specs(final_text)}
