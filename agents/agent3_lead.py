"""Agent 3 — Lead Analyst: investment thesis + sector report with adaptive thinking.

Agent 3 reads ONLY the compact summary files produced by Agent 2:
  {TICKER}_facts_latest.json  — structured KPIs (small)
  {TICKER}_brief_latest.md    — human-readable brief (small)
  {TICKER}_quote_bank.json    — top management quotes (small)

It never ingests raw filings wholesale. search_excerpts() is available for targeted
retrieval when a specific citation is needed.

Architecture (mirrors Agent 2):
  - Phase A: one isolated LLM session per company → save_analyst_report
  - Phase B: one session for the sector synthesis → save_sector_report
  If the model doesn't call the save tools, the code saves its text output as a fallback.
"""

import json
import os
import re
import sys

from config import MAX_AGENT_TURNS, FINANCIAL_DATA_DIR, FINANCIAL_ANALYSES_DIR
from llm import create_adapter
from tools import AGENT3_TOOL_DEFINITIONS, AGENT3_FUNCTIONS, execute_tool
from tools.file_tools import save_analyst_report as _save_analyst_report
from tools.file_tools import save_sector_report as _save_sector_report
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


def _build_company_report_message(project: str, company: dict, financial_data_dir: str) -> str:
    """Build the user message for a single-company analyst report session."""
    name = company["name"]
    ticker = company["ticker"].upper()
    facts_file = os.path.join(financial_data_dir, f"{ticker}_facts_latest.json")
    brief_file = os.path.join(financial_data_dir, f"{ticker}_brief_latest.md")
    quote_file = os.path.join(financial_data_dir, f"{ticker}_quote_bank.json")

    return f"""Write an investment analyst report for ONE company: {name} ({ticker}).

Project: {project}

Read these compact summary files (in order):
  1. {facts_file}   — structured KPIs with citations
  2. {brief_file}   — company brief
  3. {quote_file}   — verbatim management quotes

After reading, call save_analyst_report("{project}", "{name}", <your full report>) to save it.

Your report MUST include:
- Investment thesis (2–3 sentences)
- Key metrics summary (numbers from facts JSON, cite the file)
- Margin analysis: trend, drivers, outlook
- AI / Strategic CapEx view
- Growth outlook
- Risks (3–5, specific not generic)
- Investment stance: OVERWEIGHT / UNDERWEIGHT / NEUTRAL + one-line rationale

Do NOT fabricate numbers — only use what is in the files."""


def _run_company_report(project: str, company: dict, financial_data_dir: str) -> str:
    """Run an isolated LLM session to write one company's analyst report.

    Mirrors Agent 2's per-company isolation pattern. If the model doesn't call
    save_analyst_report, the code saves its text output directly as a fallback.

    Returns:
        The report text produced by the model.
    """
    name = company["name"]
    ticker = company["ticker"].upper()

    adapter = create_adapter(thinking=True, thinking_budget=4000)
    user_message = _build_company_report_message(project, company, financial_data_dir)
    messages = [{"role": "user", "content": user_message}]

    saved = False
    last_text = ""

    for turn in range(MAX_AGENT_TURNS):
        response = adapter.chat(messages, AGENT3_SYSTEM_PROMPT, AGENT3_TOOL_DEFINITIONS)
        if response.text:
            last_text = response.text

        print(f"    [Turn {turn + 1}] {response.stop_reason}", file=sys.stderr)

        if response.stop_reason == "tool_use":
            results = []
            for tc in response.tool_calls:
                print(f"    Tool: {tc.name}", file=sys.stderr)
                results.append(execute_tool(tc.name, tc.input, AGENT3_FUNCTIONS))
                if tc.name == "save_analyst_report":
                    saved = True
            messages.append(adapter.make_assistant_message(response))
            messages.extend(adapter.make_tool_results_messages(response.tool_calls, results))

        elif response.stop_reason == "end_turn":
            break

        else:
            print(f"    Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
            break

    # Fallback: if the model never called save_analyst_report, save its text output now.
    if not saved and last_text.strip():
        print(
            f"    [Fallback] Model did not call save_analyst_report for {ticker} — saving text output.",
            file=sys.stderr,
        )
        result = _save_analyst_report(project, name, last_text)
        if result.get("success"):
            print(f"    Analyst report saved to: {result['filepath']}", file=sys.stderr)
        else:
            print(f"    WARNING: Failed to save analyst report: {result.get('error')}", file=sys.stderr)

    return last_text


class AnalystLead:
    """Writes per-company analyst reports and a sector synthesis report.

    Phase A: one isolated LLM session per company (mirrors Agent 2's pattern).
    Phase B: one session for the sector synthesis report.

    If the model doesn't call the save tools, the code saves its text output directly.

    Args:
        project: Project name.
        companies: List of dicts with 'name' and 'ticker' keys.
        research_question: The client's primary research question.
    """

    def __init__(self, project: str, companies: list[dict], research_question: str):
        self.project = project
        self.companies = companies
        self.research_question = research_question

    def run(self) -> dict:
        """Execute the lead analyst loop.

        Returns:
            Dict with 'sector_report' text and 'viz_specs' list.
        """
        print("\n[Agent 3 — Lead Analyst] Writing investment analysis...", file=sys.stderr)
        print(f"  Project: {self.project}", file=sys.stderr)
        print(f"  Research question: {self.research_question}", file=sys.stderr)
        financial_data_dir = os.path.join(FINANCIAL_DATA_DIR, self.project)
        print(f"  Reading compact summaries from: {financial_data_dir}", file=sys.stderr)

        # ── Phase A: per-company analyst reports ──────────────────────────────
        print("\n  [Phase A] Per-company analyst reports...", file=sys.stderr)
        for company in self.companies:
            ticker = company["ticker"].upper()
            print(f"\n  ── {ticker} ──────────────────────────", file=sys.stderr)
            _run_company_report(self.project, company, financial_data_dir)
            print(f"  [Agent 3] {ticker} analyst report complete.", file=sys.stderr)

        # ── Phase B: sector synthesis report ─────────────────────────────────
        print("\n  [Phase B] Sector synthesis report...", file=sys.stderr)
        user_message = build_agent3_message(
            self.project,
            self.companies,
            self.research_question,
            financial_data_dir,
            FINANCIAL_ANALYSES_DIR,
        )
        messages = [{"role": "user", "content": user_message}]

        # Use a fresh adapter for the sector session
        adapter = create_adapter(thinking=True, thinking_budget=8000)

        last_response = None
        saved_sector_report = False

        for turn in range(MAX_AGENT_TURNS):
            print(f"  [Turn {turn + 1}] Calling LLM...", file=sys.stderr)

            response = adapter.chat(messages, AGENT3_SYSTEM_PROMPT, AGENT3_TOOL_DEFINITIONS)
            last_response = response

            print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

            if response.stop_reason == "tool_use":
                results = []
                for tc in response.tool_calls:
                    print(f"  Tool: {tc.name}({list(tc.input.keys())})", file=sys.stderr)
                    results.append(execute_tool(tc.name, tc.input, AGENT3_FUNCTIONS))
                    if tc.name == "save_sector_report":
                        saved_sector_report = True
                messages.append(adapter.make_assistant_message(response))
                messages.extend(adapter.make_tool_results_messages(response.tool_calls, results))

            elif response.stop_reason == "end_turn":
                viz_specs = _parse_viz_specs(response.text)

                # Fallback: if the model never called save_sector_report, save its text output now.
                if not saved_sector_report and response.text.strip():
                    print(
                        "  [Fallback] Model did not call save_sector_report — saving text output.",
                        file=sys.stderr,
                    )
                    result = _save_sector_report(self.project, response.text)
                    if result.get("success"):
                        print(f"  Sector report saved to: {result['filepath']}", file=sys.stderr)
                    else:
                        print(f"  WARNING: Failed to save sector report: {result.get('error')}", file=sys.stderr)

                print(
                    f"[Agent 3] Done. ({len(response.text)} chars, {len(viz_specs)} viz specs)",
                    file=sys.stderr,
                )
                return {"sector_report": response.text, "viz_specs": viz_specs}

            else:
                print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
                return {"sector_report": response.text, "viz_specs": []}

        print(f"[Agent 3] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
        final_text = last_response.text if last_response else ""
        if not saved_sector_report and final_text.strip():
            _save_sector_report(self.project, final_text)
        return {"sector_report": final_text, "viz_specs": _parse_viz_specs(final_text)}
