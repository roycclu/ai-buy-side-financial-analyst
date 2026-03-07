"""Domain-specific financial analysis tools — shared across all harnesses.

Pure Python, no framework dependencies. Each function is self-contained and
returns a plain dict suitable for JSON serialization.
"""

import json
import os
import re
import sys
from typing import Optional

import config


# ── Data loaders ─────────────────────────────────────────────────────────────

def get_company_profile(ticker: str, project: str) -> dict:
    """Load company profile dict from the extracted facts JSON.

    Returns the full facts structure as parsed from {TICKER}_facts_latest.json.
    """
    ticker = ticker.upper().strip()
    filepath = os.path.join(config.FINANCIAL_DATA_DIR, project, f"{ticker}_facts_latest.json")
    if not os.path.isfile(filepath):
        return {"error": f"Facts file not found for {ticker} in project '{project}'. Run data extraction first."}
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {"ticker": ticker, "profile": data}
    except Exception as exc:
        return {"error": f"Failed to load facts for {ticker}: {exc}"}


def get_financial_statements(ticker: str, project: str) -> dict:
    """Load full KPI table from the extracted facts JSON.

    Alias for get_company_profile — returns the complete structured data
    including income statement, balance sheet, and cash flow KPIs.
    """
    return get_company_profile(ticker, project)


def get_company_brief(ticker: str, project: str) -> dict:
    """Load the human-readable company brief markdown.

    Returns the content of {TICKER}_brief_latest.md as a text string.
    """
    ticker = ticker.upper().strip()
    filepath = os.path.join(config.FINANCIAL_DATA_DIR, project, f"{ticker}_brief_latest.md")
    if not os.path.isfile(filepath):
        return {"error": f"Brief not found for {ticker} in project '{project}'. Run data extraction first."}
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
        return {"ticker": ticker, "brief": content, "size_chars": len(content)}
    except Exception as exc:
        return {"error": f"Failed to load brief for {ticker}: {exc}"}


def get_quote_bank(ticker: str, project: str) -> dict:
    """Load management quotes from the extracted quote bank JSON.

    Returns the list of quote objects from {TICKER}_quote_bank.json.
    """
    ticker = ticker.upper().strip()
    filepath = os.path.join(config.FINANCIAL_DATA_DIR, project, f"{ticker}_quote_bank.json")
    if not os.path.isfile(filepath):
        return {"error": f"Quote bank not found for {ticker} in project '{project}'. Run data extraction first."}
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            quotes = json.load(fh)
        return {"ticker": ticker, "quotes": quotes, "count": len(quotes) if isinstance(quotes, list) else 0}
    except Exception as exc:
        return {"error": f"Failed to load quote bank for {ticker}: {exc}"}


def search_filings_by_query(ticker: str, query: str, project: str) -> dict:
    """Search local SEC filing documents for paragraphs matching a keyword query.

    Wraps tools.file_tools.search_excerpts() — finds paragraphs containing
    ALL keywords in the query string from cached raw filings.
    """
    from tools.file_tools import search_excerpts
    return search_excerpts(ticker=ticker, keywords=query, project=project)


# ── Market data ───────────────────────────────────────────────────────────────

def get_price_history(ticker: str, period: str = "1y") -> dict:
    """Fetch OHLCV price history via yfinance.

    Args:
        ticker: Stock ticker symbol.
        period: History period — e.g. "1y", "6mo", "3mo", "ytd", "max".

    Returns:
        Dict with 'history' list of {date, open, high, low, close, volume}.
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return {"error": f"No price data found for {ticker}"}
        records = []
        for date, row in hist.iterrows():
            records.append({
                "date": str(date.date()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return {"ticker": ticker, "period": period, "history": records, "points": len(records)}
    except ImportError:
        return {"error": "yfinance not installed. Run: pip install yfinance"}
    except Exception as exc:
        return {"error": f"Failed to fetch price history for {ticker}: {exc}"}


# ── Valuation tools ───────────────────────────────────────────────────────────

def compute_multiples(tickers: list, project: str) -> dict:
    """Compute valuation multiples from extracted facts data.

    Extracts whatever valuation metrics the extract phase captured in the facts JSON
    (P/E, P/FCF, EV/EBITDA, EV/Revenue, P/B). No live price data required.

    Args:
        tickers: List of ticker symbols.
        project: Project name.

    Returns:
        Dict mapping ticker → {metric_name: value} for available metrics.
    """
    _METRIC_KEYS = [
        "pe_ratio", "price_to_earnings", "price_to_fcf", "p_fcf",
        "ev_ebitda", "ev_to_ebitda", "ev_revenue", "ev_to_revenue",
        "price_to_book", "p_b",
    ]
    results = {}
    for raw_ticker in tickers:
        ticker = raw_ticker.upper().strip()
        profile = get_company_profile(ticker, project)
        if "error" in profile:
            results[ticker] = {"error": profile["error"]}
            continue
        facts = profile.get("profile", {})
        multiples = {}
        # Search top-level and nested 'valuation' sub-dict
        valuation_block = facts.get("valuation", {}) or {}
        for key in _METRIC_KEYS:
            val = facts.get(key) or valuation_block.get(key)
            if val is not None:
                multiples[key] = val
        results[ticker] = multiples or {"note": "No valuation multiples found in extracted facts."}
    return {"project": project, "multiples": results}


def run_dcf(
    ticker: str,
    project: str,
    growth_rate: float = 0.10,
    discount_rate: float = 0.10,
    terminal_growth: float = 0.03,
    years: int = 5,
) -> dict:
    """Run a simple 5-year DCF valuation using extracted free cash flow data.

    Looks for FCF in the company facts JSON under common key names.
    Returns projected FCFs, terminal value, and estimated intrinsic value.

    Args:
        ticker: Stock ticker symbol.
        project: Project name.
        growth_rate: Assumed annual FCF growth rate (default 10%).
        discount_rate: WACC / discount rate (default 10%).
        terminal_growth: Terminal perpetuity growth rate (default 3%).
        years: Projection horizon in years (default 5).

    Returns:
        Dict with DCF inputs, projected cash flows, and intrinsic_value.
    """
    profile = get_company_profile(ticker, project)
    if "error" in profile:
        return profile

    facts = profile.get("profile", {})
    cash_flow_block = facts.get("cash_flow", {}) or {}

    # Try to extract FCF from various possible key names
    _FCF_KEYS = ["free_cash_flow", "fcf", "levered_free_cash_flow", "free_cash_flow_ttm"]
    fcf_raw = None
    for key in _FCF_KEYS:
        val = facts.get(key) or cash_flow_block.get(key)
        if val is not None:
            fcf_raw = val
            break

    if fcf_raw is None:
        return {
            "error": (
                f"No FCF data found for {ticker} in project '{project}'. "
                "Run data extraction first, or check that the extract phase captured free_cash_flow."
            )
        }

    # Parse numeric value (handles strings like "$45.3B", "45300M", "45,300")
    try:
        s = str(fcf_raw).replace(",", "").replace("$", "").strip()
        if s.upper().endswith("B"):
            fcf = float(s[:-1]) * 1e9
        elif s.upper().endswith("M"):
            fcf = float(s[:-1]) * 1e6
        elif s.upper().endswith("K"):
            fcf = float(s[:-1]) * 1e3
        else:
            fcf = float(s)
    except (ValueError, AttributeError):
        return {"error": f"Could not parse FCF value '{fcf_raw}' for {ticker}"}

    # Project FCFs and compute PV
    projected = []
    pv_sum = 0.0
    for i in range(1, years + 1):
        cf = fcf * ((1 + growth_rate) ** i)
        pv = cf / ((1 + discount_rate) ** i)
        projected.append({"year": i, "fcf": round(cf, 0), "pv": round(pv, 0)})
        pv_sum += pv

    # Terminal value (Gordon Growth)
    terminal_fcf = fcf * ((1 + growth_rate) ** years) * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    terminal_pv = terminal_value / ((1 + discount_rate) ** years)

    intrinsic_value = pv_sum + terminal_pv

    return {
        "ticker": ticker,
        "base_fcf": round(fcf, 0),
        "growth_rate": growth_rate,
        "discount_rate": discount_rate,
        "terminal_growth": terminal_growth,
        "years": years,
        "projected_fcfs": projected,
        "terminal_value": round(terminal_value, 0),
        "terminal_pv": round(terminal_pv, 0),
        "pv_of_fcfs": round(pv_sum, 0),
        "intrinsic_value": round(intrinsic_value, 0),
    }


# ── Extract phase internals ───────────────────────────────────────────────────

# Per-company session trim threshold (one company at a time)
_MAX_HISTORY_CHARS = 150_000  # ~37k tokens; safety net if filings are very large

# How many times to re-prompt the model when it produces output without the required XML tags
# or skips the tool-call reading step entirely.
_MAX_FORMAT_RETRIES = 2

# Maps internal section key → XML tag name used in the prompt / parser
_SECTION_TAGS = {
    "facts":  "company_facts",
    "brief":  "company_brief",
    "quotes": "quote_bank",
}


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
    from tools.file_tools import save_company_facts, save_company_brief, save_quote_bank

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


def _build_retry_message(missing: list[str], tools_were_called: bool) -> str:
    """Build a corrective follow-up message when the model produced bad output.

    Two cases:
    - tools_were_called=False: model skipped the file-reading steps entirely.
    - tools_were_called=True:  model read files but didn't use the XML output format.
    """
    if not tools_were_called:
        return (
            "You did not call any tools. You MUST follow the mandatory sequence:\n"
            "1. Call list_files on the filing directory.\n"
            "2. Call read_file on the most recent 10-K.\n"
            "3. Call read_file on the most recent 10-Q.\n"
            "Only after those tool calls, write your response using the three XML tags: "
            "<company_facts>...</company_facts>, <company_brief>...</company_brief>, "
            "<quote_bank>...</quote_bank>. Do not output anything before completing the tool calls."
        )
    missing_tags = ", ".join(
        f"<{_SECTION_TAGS[k]}>...</{_SECTION_TAGS[k]}>" for k in missing
    )
    return (
        f"Your response was missing required XML output sections: {missing_tags}.\n"
        "Please re-emit your complete analysis right now using ONLY these three XML tags "
        "and no other text:\n\n"
        "<company_facts>\n"
        "{ valid JSON object with all KPI fields }\n"
        "</company_facts>\n\n"
        "<company_brief>\n"
        "## CompanyName (TICKER) — Quarter Brief\n"
        "... markdown content ...\n"
        "</company_brief>\n\n"
        "<quote_bank>\n"
        '[{"speaker": "...", "context": "...", "quote": "...", "relevance": "..."}]\n'
        "</quote_bank>\n\n"
        "Do NOT use asterisks, curly-brace pseudocode, or any notation other than these "
        "exact XML tags. Base all numbers on the filing content you already read."
    )


def _data_already_extracted(ticker: str, project: str) -> bool:
    """Check whether all three extract-phase output files already exist for this company.

    Args:
        ticker: Stock ticker symbol.
        project: Project name (used for project-scoped file paths).

    Returns:
        True if facts, brief, and quote bank files all exist.
    """
    ticker_upper = ticker.upper().strip()
    data_dir = os.path.join(config.FINANCIAL_DATA_DIR, project)
    required = [
        f"{ticker_upper}_facts_latest.json",
        f"{ticker_upper}_brief_latest.md",
        f"{ticker_upper}_quote_bank.json",
    ]
    return all(os.path.isfile(os.path.join(data_dir, f)) for f in required)


def _run_for_company(company: dict, project: str) -> str:
    """Run a fresh, isolated LLM session to process a single company.

    The LLM reads filings via tool calls (list_files / read_file), then outputs
    three XML-tagged sections in its final text.  _parse_and_save_outputs()
    extracts those sections and writes the files — no save tools required.

    If the model skips the tool-call reading step or produces output without the
    required XML tags, a corrective follow-up message is appended and the loop
    continues.  This retries up to _MAX_FORMAT_RETRIES times.

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
    from llm import create_adapter
    from tools import EXTRACT_TOOL_DEFINITIONS, EXTRACT_FUNCTIONS, execute_tool
    from utils.prompts import EXTRACT_SYSTEM_PROMPT, build_extract_message

    ticker = company["ticker"].upper().strip()

    # Fresh adapter per company — no shared state between sessions
    adapter = create_adapter(thinking=True, thinking_budget=4000)

    financial_files_dir = os.path.join(config.FINANCIAL_FILES_DIR, project)
    financial_data_dir = os.path.join(config.FINANCIAL_DATA_DIR, project)
    user_message = build_extract_message(company, financial_files_dir, financial_data_dir, project)
    messages = [{"role": "user", "content": user_message}]

    final_text = ""
    tools_called_this_session = False
    format_retries = 0

    for turn in range(config.MAX_AGENT_TURNS):
        messages = _trim_tool_results(messages)
        response = adapter.chat(messages, EXTRACT_SYSTEM_PROMPT, EXTRACT_TOOL_DEFINITIONS)

        print(f"    [Turn {turn + 1}] {response.stop_reason}", file=sys.stderr)

        if response.stop_reason == "tool_use":
            tools_called_this_session = True
            results = []
            for tc in response.tool_calls:
                print(f"    Tool: {tc.name}", file=sys.stderr)
                results.append(execute_tool(tc.name, tc.input, EXTRACT_FUNCTIONS))
            messages.append(adapter.make_assistant_message(response))
            messages.extend(adapter.make_tool_results_messages(response.tool_calls, results))

        elif response.stop_reason == "end_turn":
            final_text = response.text

            # Try to parse the three XML sections and save files
            saved = _parse_and_save_outputs(final_text, ticker, project)
            missing = [k for k, v in saved.items() if not v]

            if not missing:
                # All three sections found and saved — done
                print(f"    All 3 output files saved for {ticker}.", file=sys.stderr)
                return final_text

            # Something is missing — decide whether to retry
            if format_retries >= _MAX_FORMAT_RETRIES:
                print(
                    f"    WARNING: {ticker} — gave up after {format_retries} format "
                    f"retries; still missing: {missing}",
                    file=sys.stderr,
                )
                return final_text

            format_retries += 1
            print(
                f"    [Format retry {format_retries}/{_MAX_FORMAT_RETRIES}] "
                f"tools_called={tools_called_this_session}, missing={missing}",
                file=sys.stderr,
            )
            corrective = _build_retry_message(missing, tools_called_this_session)
            messages.append(adapter.make_assistant_message(response))
            messages.append({"role": "user", "content": corrective})
            # Do NOT break — continue the loop with the corrective message appended

        else:
            print(f"    Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
            final_text = response.text
            return final_text

    print(f"    Warning: reached max turns ({config.MAX_AGENT_TURNS}) for {ticker}", file=sys.stderr)
    return final_text


def extract_all_companies(companies: list[dict], project: str) -> str:
    """Run the extract phase for all companies, one isolated LLM session each.

    Replaces AnalystAgent.run(). Each company is processed in a separate LLM
    session to prevent context accumulation. Skips companies whose output files
    already exist.

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
        project: Project name (used for project-scoped file paths).

    Returns:
        Combined summary string for all companies.
    """
    print("\n[Extract Phase] Extracting compact company summaries...", file=sys.stderr)
    print(f"  Companies: {[c['ticker'] for c in companies]}", file=sys.stderr)
    print(f"  Project: {project}", file=sys.stderr)
    print(f"  Strategy: one isolated LLM session per company; files saved by orchestrator", file=sys.stderr)

    summaries = []
    for company in companies:
        ticker = company["ticker"]
        print(f"\n  ── {ticker} ──────────────────────────", file=sys.stderr)

        if _data_already_extracted(ticker, project):
            print(f"  [Extract] {ticker}: all 3 data files already exist — skipping extraction.", file=sys.stderr)
            summaries.append(f"=== {ticker} ===\n[Skipped — data already extracted]")
            continue

        result = _run_for_company(company, project)
        summaries.append(f"=== {ticker} ===\n{result}")
        print(f"  [Extract] {ticker} complete.", file=sys.stderr)

    print(f"\n[Extract Phase] All {len(companies)} companies processed.", file=sys.stderr)
    return "\n\n".join(summaries)


# ── Bridge: single-company extraction (used by framework harnesses) ───────────

def run_company_data_extraction(ticker: str, project: str) -> dict:
    """Run the full data extraction for a single company.

    This is the key bridge between harnesses and the native extraction logic.
    Calls _run_for_company() — an isolated LLM session that reads raw filings,
    parses XML output, and saves all three output files:
      {TICKER}_facts_latest.json
      {TICKER}_brief_latest.md
      {TICKER}_quote_bank.json

    Args:
        ticker: Stock ticker symbol.
        project: Project name.

    Returns:
        Dict with status ("complete", "skipped", or "error") and a summary.
    """
    ticker = ticker.upper().strip()
    print(f"[run_company_data_extraction] {ticker} — project: {project}", file=sys.stderr)

    if _data_already_extracted(ticker, project):
        return {
            "ticker": ticker,
            "status": "skipped",
            "message": "All 3 data files already exist — skipping extraction.",
        }

    company = {"name": ticker, "ticker": ticker}
    try:
        result_text = _run_for_company(company, project)
        return {
            "ticker": ticker,
            "status": "complete",
            "summary": result_text[:500] if result_text else "",
        }
    except Exception as exc:
        return {"ticker": ticker, "status": "error", "error": str(exc)}
