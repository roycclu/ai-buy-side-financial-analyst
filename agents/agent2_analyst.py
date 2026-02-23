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
"""

import sys

from config import MAX_AGENT_TURNS, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR
from llm import create_adapter
from tools import AGENT2_TOOL_DEFINITIONS, AGENT2_FUNCTIONS, execute_tool
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


def _run_for_company(company: dict) -> str:
    """Run a fresh, isolated LLM session to process a single company.

    Produces three compact files:
      {TICKER}_facts_latest.json  — structured KPI table with citations
      {TICKER}_brief_latest.md    — 800-1500 token human-readable summary
      {TICKER}_quote_bank.json    — top 5-10 management quotes

    Args:
        company: Dict with 'name' and 'ticker' keys.

    Returns:
        Agent's final summary text for this company.
    """
    # Fresh adapter per company — no shared state between sessions
    adapter = create_adapter(thinking=True, thinking_budget=4000)

    user_message = build_agent2_message(company, FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR)
    messages = [{"role": "user", "content": user_message}]

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
            return response.text

        else:
            print(f"    Unexpected stop reason: {response.stop_reason}", file=sys.stderr)
            return response.text

    print(f"    Warning: reached max turns ({MAX_AGENT_TURNS}) for {company['ticker']}", file=sys.stderr)
    return response.text if response else ""


class AnalystAgent:
    """Reads local filings and produces compact CompanyFacts + CompanyBrief + QuoteBank.

    Each company is processed in a SEPARATE isolated LLM session, preventing context
    accumulation across companies and keeping every session well under the 200k limit.

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
    """

    def __init__(self, companies: list[dict]):
        self.companies = companies

    def run(self) -> str:
        """Run one isolated session per company and return a combined summary."""
        print("\n[Agent 2 — Analyst] Extracting compact company summaries...", file=sys.stderr)
        print(f"  Companies: {[c['ticker'] for c in self.companies]}", file=sys.stderr)
        print(f"  Strategy: one isolated LLM session per company", file=sys.stderr)

        summaries = []
        for company in self.companies:
            ticker = company["ticker"]
            print(f"\n  ── {ticker} ──────────────────────────", file=sys.stderr)
            result = _run_for_company(company)
            summaries.append(f"=== {ticker} ===\n{result}")
            print(f"  [Agent 2] {ticker} complete.", file=sys.stderr)

        print(f"\n[Agent 2] All {len(self.companies)} companies processed.", file=sys.stderr)
        return "\n\n".join(summaries)
