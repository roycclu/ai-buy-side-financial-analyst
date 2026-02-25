"""Agent 2 — Analyst Agent: per-company data extractor with adaptive thinking.

Each company runs in its OWN isolated LLM session.  This is the core fix for the
200k-token overflow problem: instead of one long session processing all companies
sequentially (with all their raw filing content accumulating in message history),
we start a fresh conversation for each ticker.

Per-company context budget (rough estimate):
  system prompt   ~  2k tokens
  user message    ~  0.2k tokens
  10-K read       ~ 10k tokens (40k chars / 4 chars per token)
  10-Q read       ~ 10k tokens
  tool results    ~  5k tokens
  output (3 files)~  4k tokens
  thinking        ~  4k tokens
  ─────────────────────────────
  total per co.   ~ 35k tokens   ← well under the 200k limit

File-saving design: Agent 2 does NOT rely on the LLM to call save tools.
Instead the LLM outputs three XML-tagged sections in its final text response,
and _parse_and_save_outputs() extracts and saves them directly in Python.
"""

import os
import re
import sys

from config import MAX_AGENT_TURNS, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR
from llm import create_adapter
from tools import AGENT2_TOOL_DEFINITIONS, AGENT2_FUNCTIONS, execute_tool
from tools.file_tools import save_company_facts, save_company_brief, save_quote_bank
from utils.prompts import AGENT2_SYSTEM_PROMPT, build_agent2_message

# Per-company session trim threshold (much lower than before — one company at a time)
_MAX_HISTORY_CHARS = 150_000  # ~37k tokens; safety net if filings are very large


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


def _extract_tagged_section(text: str, tag: str) -> str | None:
    """Extract the content between <tag> and </tag> from text.

    Also strips surrounding markdown code-fence markers (```json / ```) if present.
    Returns None if the tag is not found.
    """
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    content = match.group(1).strip()
    # Strip optional markdown code fences (```json ... ``` or ``` ... ```)
    content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
    content = re.sub(r"\n?```$", "", content)
    return content.strip()


def _parse_and_save_outputs(text: str, ticker: str, project: str) -> dict[str, bool]:
    """Parse the LLM's text response and save the three output files directly.

    Looks for <company_facts>, <company_brief>, and <quote_bank> XML sections.
    Calls the save functions in Python — no LLM tool calls involved.

    Args:
        text: The full text response from the LLM.
        ticker: Stock ticker symbol (e.g. 'MSFT').
        project: Project name (parent subfolder under Financial Data).

    Returns:
        Dict mapping section name to True (saved) / False (missing or failed).
    """
    ticker_upper = ticker.upper().strip()
    saved = {"facts": False, "brief": False, "quotes": False}

    facts_content = _extract_tagged_section(text, "company_facts")
    if facts_content:
        result = save_company_facts(ticker_upper, facts_content, project)
        saved["facts"] = result.get("success", False)
        if saved["facts"]:
            print(f"    Saved: {result['filepath']}", file=sys.stderr)
        else:
            print(f"    ERROR saving facts: {result.get('error')}", file=sys.stderr)
    else:
        print(f"    WARNING: <company_facts> section not found in LLM response for {ticker_upper}", file=sys.stderr)

    brief_content = _extract_tagged_section(text, "company_brief")
    if brief_content:
        result = save_company_brief(ticker_upper, brief_content, project)
        saved["brief"] = result.get("success", False)
        if saved["brief"]:
            print(f"    Saved: {result['filepath']}", file=sys.stderr)
        else:
            print(f"    ERROR saving brief: {result.get('error')}", file=sys.stderr)
    else:
        print(f"    WARNING: <company_brief> section not found in LLM response for {ticker_upper}", file=sys.stderr)

    quote_content = _extract_tagged_section(text, "quote_bank")
    if quote_content:
        result = save_quote_bank(ticker_upper, quote_content, project)
        saved["quotes"] = result.get("success", False)
        if saved["quotes"]:
            print(f"    Saved: {result['filepath']}", file=sys.stderr)
        else:
            print(f"    ERROR saving quote bank: {result.get('error')}", file=sys.stderr)
    else:
        print(f"    WARNING: <quote_bank> section not found in LLM response for {ticker_upper}", file=sys.stderr)

    return saved


def _run_for_company(company: dict, project: str) -> str:
    """Run a fresh, isolated LLM session to process a single company.

    The LLM reads filings via tool calls (list_files / read_file), then outputs
    three XML-tagged sections in its final text.  _parse_and_save_outputs()
    extracts those sections and writes the files — no save tools required.

    Produces three compact files:
      {TICKER}_facts_latest.json  — structured KPI table with citations
      {TICKER}_brief_latest.md    — 800-1500 token human-readable summary
      {TICKER}_quote_bank.json    — top 5-10 management quotes

    Args:
        company: Dict with 'name' and 'ticker' keys.
        project: Project name (used for project-scoped file paths).

    Returns:
        Agent's final summary text for this company.
    """
    ticker = company["ticker"].upper().strip()

    # Fresh adapter per company — no shared state between sessions
    adapter = create_adapter(thinking=True, thinking_budget=4000)

    financial_files_dir = os.path.join(FINANCIAL_FILES_DIR, project)
    financial_data_dir = os.path.join(FINANCIAL_DATA_DIR, project)
    user_message = build_agent2_message(company, financial_files_dir, financial_data_dir, project)
    messages = [{"role": "user", "content": user_message}]

    final_text = ""
    for turn in range(MAX_AGENT_TURNS):
        messages = _trim_tool_results(messages)
        response = adapter.chat(messages, AGENT2_SYSTEM_PROMPT, AGENT2_TOOL_DEFINITIONS)

        print(f"    [Turn {turn + 1}] {response.stop_reason}", file=sys.stderr)

        if response.stop_reason == "tool_use":
            results = []
            for tc in response.tool_calls:
                print(f"    Tool: {tc.name}", file=sys.stderr)
                results.append(execute_tool(tc.name, tc.input, AGENT2_FUNCTIONS))
            messages.append(adapter.make_assistant_message(response))
            messages.extend(adapter.make_tool_results_messages(response.tool_calls, results))

        elif response.stop_reason == "end_turn":
            final_text = response.text
            break

        else:
            print(f"    Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
            final_text = response.text
            break
    else:
        print(f"    Warning: reached max turns ({MAX_AGENT_TURNS}) for {ticker}", file=sys.stderr)
        final_text = response.text if response else ""

    # Parse structured output and save files — no LLM tool calls needed
    saved = _parse_and_save_outputs(final_text, ticker, project)
    missing = [k for k, v in saved.items() if not v]
    if missing:
        print(f"    WARNING: {ticker} — sections not saved: {missing}", file=sys.stderr)
    else:
        print(f"    All 3 output files saved for {ticker}.", file=sys.stderr)

    return final_text


def _data_already_extracted(ticker: str, project: str) -> bool:
    """Check whether all three Agent 2 output files already exist for this company.

    Args:
        ticker: Stock ticker symbol.
        project: Project name (used for project-scoped file paths).

    Returns:
        True if facts, brief, and quote bank files all exist.
    """
    ticker_upper = ticker.upper().strip()
    data_dir = os.path.join(FINANCIAL_DATA_DIR, project)
    required = [
        f"{ticker_upper}_facts_latest.json",
        f"{ticker_upper}_brief_latest.md",
        f"{ticker_upper}_quote_bank.json",
    ]
    return all(os.path.isfile(os.path.join(data_dir, f)) for f in required)


class AnalystAgent:
    """Reads local filings and produces compact CompanyFacts + CompanyBrief + QuoteBank.

    Each company is processed in a SEPARATE isolated LLM session, preventing context
    accumulation across companies and keeping every session well under the 200k limit.

    File saving is handled by Python code (not LLM tool calls): the LLM outputs
    structured XML-tagged sections, which are parsed and written by _parse_and_save_outputs().

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
        project: Project name (used for project-scoped file paths).
    """

    def __init__(self, companies: list[dict], project: str):
        self.companies = companies
        self.project = project

    def run(self) -> str:
        """Run one isolated session per company and return a combined summary."""
        print("\n[Agent 2 — Analyst] Extracting compact company summaries...", file=sys.stderr)
        print(f"  Companies: {[c['ticker'] for c in self.companies]}", file=sys.stderr)
        print(f"  Project: {self.project}", file=sys.stderr)
        print(f"  Strategy: one isolated LLM session per company; files saved by orchestrator", file=sys.stderr)

        summaries = []
        for company in self.companies:
            ticker = company["ticker"]
            print(f"\n  ── {ticker} ──────────────────────────", file=sys.stderr)

            if _data_already_extracted(ticker, self.project):
                print(f"  [Agent 2] {ticker}: all 3 data files already exist — skipping extraction.", file=sys.stderr)
                summaries.append(f"=== {ticker} ===\n[Skipped — data already extracted]")
                continue

            result = _run_for_company(company, self.project)
            summaries.append(f"=== {ticker} ===\n{result}")
            print(f"  [Agent 2] {ticker} complete.", file=sys.stderr)

        print(f"\n[Agent 2] All {len(self.companies)} companies processed.", file=sys.stderr)
        return "\n\n".join(summaries)
