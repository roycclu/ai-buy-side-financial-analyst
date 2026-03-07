"""Native harness — runs the full buy-side research pipeline without any framework.

NativeWorkflow owns the LLM loops for research (phase 1), analysis (phase 3),
and visualization (phase 4). The extract phase (phase 2) is delegated to
tools/financial_analysis.py which runs one isolated session per company.

Pipeline:
    Phase 1 — collect raw filings (cache-first)          ← _run_research_phase()
    Phase 2 — extract compact data per company            ← extract_all_companies()
    Phase 3 — write analyst + sector reports → viz specs  ← _run_analysis_phase()
    Phase 4 — generate charts                             ← _run_visualization_phase()
"""

import json
import os
import re
import sys

from config import MAX_AGENT_TURNS, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR, FINANCIAL_ANALYSES_DIR
from llm import create_adapter
from tools import (
    RESEARCH_TOOL_DEFINITIONS, RESEARCH_FUNCTIONS,
    ANALYSIS_TOOL_DEFINITIONS, ANALYSIS_FUNCTIONS,
    get_viz_tool_definitions, get_viz_functions,
    execute_tool,
)
from tools.financial_analysis import extract_all_companies
from tools.file_tools import save_analyst_report as _save_analyst_report
from tools.file_tools import save_sector_report as _save_sector_report
from utils.prompts import (
    RESEARCH_SYSTEM_PROMPT, build_research_message,
    ANALYSIS_SYSTEM_PROMPT, build_analysis_message,
    VIZ_SYSTEM_PROMPT, build_viz_message,
)
from observability.arize_logger import setup_observability


# ── Phase 1 helpers ───────────────────────────────────────────────────────────

def _run_research_phase(companies: list[dict], project: str) -> str:
    """Run the research LLM loop to collect SEC filings."""
    print("\n[Phase 1 — Research] Starting SEC EDGAR filing collection...", file=sys.stderr)
    print(f"  Companies: {[c['ticker'] for c in companies]}", file=sys.stderr)
    print(f"  Project: {project}", file=sys.stderr)

    adapter = create_adapter(thinking=False)
    financial_files_dir = os.path.join(FINANCIAL_FILES_DIR, project)
    user_message = build_research_message(companies, financial_files_dir, project)
    messages = [{"role": "user", "content": user_message}]

    for turn in range(MAX_AGENT_TURNS):
        print(f"  [Turn {turn + 1}] Calling LLM...", file=sys.stderr)

        response = adapter.chat(messages, RESEARCH_SYSTEM_PROMPT, RESEARCH_TOOL_DEFINITIONS)

        print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

        if response.stop_reason == "tool_use":
            results = []
            for tc in response.tool_calls:
                print(f"  Tool: {tc.name}({tc.input})", file=sys.stderr)
                results.append(execute_tool(tc.name, tc.input, RESEARCH_FUNCTIONS))
            messages.append(adapter.make_assistant_message(response))
            messages.extend(adapter.make_tool_results_messages(response.tool_calls, results))

        elif response.stop_reason == "end_turn":
            print(f"[Phase 1] Done. ({len(response.text)} chars)", file=sys.stderr)
            return response.text

        else:
            print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
            return response.text

    print(f"[Phase 1] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
    return response.text if response else ""


# ── Phase 3 helpers ───────────────────────────────────────────────────────────

def _analyst_report_path(project: str, company_name: str) -> str:
    """Return the expected filesystem path for a company's analyst report."""
    company_safe = company_name.lower().replace(" ", "_")
    return os.path.join(
        FINANCIAL_ANALYSES_DIR, project, "analyst_reports",
        f"{company_safe}_analyst_report.md",
    )


def _sector_report_path(project: str) -> str:
    """Return the expected filesystem path for the sector report."""
    return os.path.join(FINANCIAL_ANALYSES_DIR, project, "sector_reports", "sector_report.md")


def _viz_specs_path(project: str) -> str:
    """Return the path used to persist viz_specs between runs."""
    return os.path.join(FINANCIAL_ANALYSES_DIR, project, "viz_specs.json")


def _save_viz_specs(project: str, viz_specs: list[dict]) -> None:
    """Persist viz_specs to a JSON file so the next run can skip Phase B."""
    path = _viz_specs_path(project)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(viz_specs, fh, indent=2)


def _load_viz_specs(project: str) -> list[dict]:
    """Load persisted viz_specs; return [] if the file doesn't exist or is unreadable."""
    path = _viz_specs_path(project)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def _parse_viz_specs(text: str) -> list[dict]:
    """Extract the JSON viz_specs block from the analysis phase output."""
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

    Mirrors the extract phase per-company isolation pattern. If the model doesn't call
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
        response = adapter.chat(messages, ANALYSIS_SYSTEM_PROMPT, ANALYSIS_TOOL_DEFINITIONS)
        if response.text:
            last_text = response.text

        print(f"    [Turn {turn + 1}] {response.stop_reason}", file=sys.stderr)

        if response.stop_reason == "tool_use":
            results = []
            for tc in response.tool_calls:
                print(f"    Tool: {tc.name}", file=sys.stderr)
                results.append(execute_tool(tc.name, tc.input, ANALYSIS_FUNCTIONS))
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


def _run_analysis_phase(project: str, companies: list[dict], research_question: str) -> dict:
    """Run the analysis LLM loops (per-company reports + sector synthesis).

    Phase A: one isolated LLM session per company → save_analyst_report
    Phase B: one session for the sector synthesis → save_sector_report

    Returns:
        Dict with 'sector_report' text and 'viz_specs' list.
    """
    print("\n[Phase 3 — Analysis] Writing investment analysis...", file=sys.stderr)
    print(f"  Project: {project}", file=sys.stderr)
    print(f"  Research question: {research_question}", file=sys.stderr)
    financial_data_dir = os.path.join(FINANCIAL_DATA_DIR, project)
    print(f"  Reading compact summaries from: {financial_data_dir}", file=sys.stderr)

    # ── Phase A: per-company analyst reports ──────────────────────────────
    print("\n  [Phase A] Per-company analyst reports...", file=sys.stderr)
    for company in companies:
        ticker = company["ticker"].upper()
        name = company["name"]
        report_path = _analyst_report_path(project, name)
        if os.path.isfile(report_path):
            print(
                f"  [Phase 3] {ticker}: analyst report already exists — skipping.",
                file=sys.stderr,
            )
            continue
        print(f"\n  ── {ticker} ──────────────────────────", file=sys.stderr)
        _run_company_report(project, company, financial_data_dir)
        print(f"  [Phase 3] {ticker} analyst report complete.", file=sys.stderr)

    # ── Phase B: sector synthesis report ─────────────────────────────────
    print("\n  [Phase B] Sector synthesis report...", file=sys.stderr)

    # If the sector report already exists, skip the LLM call and reload viz_specs.
    sector_path = _sector_report_path(project)
    if os.path.isfile(sector_path):
        print(
            "  [Phase 3] Sector report already exists — skipping LLM call.",
            file=sys.stderr,
        )
        with open(sector_path, encoding="utf-8") as fh:
            cached_sector = fh.read()
        viz_specs = _load_viz_specs(project)
        if not viz_specs:
            # Fall back to parsing the text if the JSON file is missing
            viz_specs = _parse_viz_specs(cached_sector)
        print(
            f"[Phase 3] Loaded from cache. ({len(cached_sector)} chars, "
            f"{len(viz_specs)} viz specs)",
            file=sys.stderr,
        )
        return {"sector_report": cached_sector, "viz_specs": viz_specs}

    user_message = build_analysis_message(
        project,
        companies,
        research_question,
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

        response = adapter.chat(messages, ANALYSIS_SYSTEM_PROMPT, ANALYSIS_TOOL_DEFINITIONS)
        last_response = response

        print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

        if response.stop_reason == "tool_use":
            results = []
            for tc in response.tool_calls:
                print(f"  Tool: {tc.name}({list(tc.input.keys())})", file=sys.stderr)
                results.append(execute_tool(tc.name, tc.input, ANALYSIS_FUNCTIONS))
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
                result = _save_sector_report(project, response.text)
                if result.get("success"):
                    print(f"  Sector report saved to: {result['filepath']}", file=sys.stderr)
                else:
                    print(f"  WARNING: Failed to save sector report: {result.get('error')}", file=sys.stderr)

            # Persist viz_specs so the next run can skip Phase B entirely.
            if viz_specs:
                _save_viz_specs(project, viz_specs)

            print(
                f"[Phase 3] Done. ({len(response.text)} chars, {len(viz_specs)} viz specs)",
                file=sys.stderr,
            )
            return {"sector_report": response.text, "viz_specs": viz_specs}

        else:
            print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
            return {"sector_report": response.text, "viz_specs": []}

    print(f"[Phase 3] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
    final_text = last_response.text if last_response else ""
    if not saved_sector_report and final_text.strip():
        _save_sector_report(project, final_text)
    viz_specs = _parse_viz_specs(final_text)
    if viz_specs:
        _save_viz_specs(project, viz_specs)
    return {"sector_report": final_text, "viz_specs": viz_specs}


# ── Phase 4 helpers ───────────────────────────────────────────────────────────

def _run_visualization_phase(project: str, viz_specs: list[dict]) -> str:
    """Run the visualization LLM loop to generate charts."""
    if not viz_specs:
        print("[Phase 4 — Visualization] No viz specs provided — skipping.", file=sys.stderr)
        return "No visualizations requested."

    print(
        f"\n[Phase 4 — Visualization] Creating {len(viz_specs)} chart(s)...",
        file=sys.stderr,
    )

    adapter = create_adapter(thinking=False)
    financial_data_dir = os.path.join(FINANCIAL_DATA_DIR, project)
    user_message = build_viz_message(
        project,
        viz_specs,
        financial_data_dir,
        FINANCIAL_ANALYSES_DIR,
    )
    messages = [{"role": "user", "content": user_message}]
    tool_definitions = get_viz_tool_definitions()
    tool_functions = get_viz_functions()

    for turn in range(MAX_AGENT_TURNS):
        print(f"  [Turn {turn + 1}] Calling LLM...", file=sys.stderr)

        response = adapter.chat(messages, VIZ_SYSTEM_PROMPT, tool_definitions)

        print(f"  Stop reason: {response.stop_reason}", file=sys.stderr)

        if response.stop_reason == "tool_use":
            results = []
            for tc in response.tool_calls:
                print(f"  Tool: {tc.name}({tc.input})", file=sys.stderr)
                results.append(execute_tool(tc.name, tc.input, tool_functions))
            messages.append(adapter.make_assistant_message(response))
            messages.extend(adapter.make_tool_results_messages(response.tool_calls, results))

        elif response.stop_reason == "end_turn":
            print(f"[Phase 4] Done. ({len(response.text)} chars)", file=sys.stderr)
            return response.text

        else:
            print(f"  Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
            return response.text

    print(f"[Phase 4] Warning: reached max turns ({MAX_AGENT_TURNS})", file=sys.stderr)
    return response.text if response else ""


# ── NativeWorkflow ────────────────────────────────────────────────────────────

class NativeWorkflow:
    """Runs the full buy-side research pipeline without any framework.

    Pipeline:
        Phase 1 — collect raw filings (cache-first)
        Phase 2 — extract compact CompanyFacts + CompanyBrief + QuoteBank per company
                  (one isolated LLM session per company to prevent context overflow)
        Phase 3 — write analyst + sector reports from compact summaries → viz specs
        Phase 4 — generate charts

    Args:
        project: Project name (used for output subdirectory).
        companies: List of dicts with 'name' and 'ticker' keys.
        research_question: The client's primary research question.
    """

    def __init__(self, project: str, companies: list[dict], research_question: str):
        self.project = project
        self.companies = companies
        self.research_question = research_question

    def run(self):
        """Execute the full pipeline."""
        setup_observability("native")

        print("\n[Workflow] Phase 1/4 — Filing Collection", file=sys.stderr)
        research_summary = _run_research_phase(self.companies, self.project)

        print("\n[Workflow] Phase 2/4 — Compact Data Extraction (per-company sessions)", file=sys.stderr)
        data_summary = extract_all_companies(self.companies, self.project)

        print("\n[Workflow] Phase 3/4 — Investment Analysis", file=sys.stderr)
        analysis_result = _run_analysis_phase(
            self.project, self.companies, self.research_question
        )
        viz_specs = analysis_result.get("viz_specs", [])

        print("\n[Workflow] Phase 4/4 — Chart Generation", file=sys.stderr)
        viz_summary = _run_visualization_phase(self.project, viz_specs)

        print("\n[Workflow] All phases complete.", file=sys.stderr)

        return {
            "research_summary": research_summary,
            "data_summary": data_summary,
            "sector_report": analysis_result.get("sector_report", ""),
            "viz_summary": viz_summary,
            "viz_specs": viz_specs,
        }
