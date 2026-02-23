# Buy-Side Financial Analyst Agent Team

A production-quality, multi-agent buy-side financial research system powered by
**Claude Opus 4.6** with adaptive thinking and SEC EDGAR data.

## What It Does

Five coordinated AI agents mimic a real research function:

1. **Agent 0 — Project Manager**: CLI interface for project setup and orchestration
2. **Agent 1 — Research Agent**: Fetches SEC EDGAR filings (10-K, 10-Q) with cache-first logic
3. **Agent 2 — Analyst Agent**: Extracts compact CompanyFacts + CompanyBrief + QuoteBank per company
4. **Agent 3 — Lead Analyst**: Writes per-company analyst reports and a sector synthesis from compact summaries
5. **Agent 4 — Visualization Agent**: Generates professional charts (bar, line, comparison)

All outputs are cached. Arize Phoenix provides local observability at `http://localhost:6006`.

---

## Setup

### 1. Install dependencies

```bash
cd "Buy Side Financial Analyst"
pip install -r requirements.txt
```

### 2. Set your API key

```bash
export ANTHROPIC_API_KEY=your_key_here
# or copy .env.example to .env and fill it in
```

### 3. Run

```bash
python main.py
```

---

## Quick Start Example

```
$ python main.py

What would you like to do?
  [1] Start a new project
  [2] Continue an existing project

Enter 1 or 2: 1

── NEW PROJECT SETUP ──────────────────────────────────────
Project name: AI_Capex_2025
Companies: Microsoft Corporation:MSFT, Apple Inc:AAPL
Research question: Which company has stronger AI capex growth?
```

---

## Output Structure

```
Financial Files/
└── MSFT/10K/, MSFT/10Q/, AAPL/10K/, AAPL/10Q/    ← raw filings (cached, not read by Agent 3)

Financial Data/
├── MSFT_facts_latest.json    ← structured KPI table + citations
├── MSFT_brief_latest.md      ← 800-1500 token company summary
├── MSFT_quote_bank.json      ← top 5-10 management quotes
├── AAPL_facts_latest.json
├── AAPL_brief_latest.md
└── AAPL_quote_bank.json

Financial Analyses/AI_Capex_2025/
├── analyst_reports/
│   ├── microsoft_corporation_analyst_report.md
│   └── apple_inc_analyst_report.md
├── sector_reports/
│   └── sector_report.md
└── visualizations/
    └── *.png
```

---

## Architecture: Token-Efficient Two-Layer Design

### The Problem (Before)

Agent 2 would read all raw SEC filings (up to 40k chars each) for all companies into a
single LLM session. With 3+ companies × 2 filings each, sessions regularly hit the
200k context limit before the agent finished writing output.

Agent 3 then read those large markdown files for cross-company synthesis — compounding
the token pressure.

### The Solution (Now)

**Agent 2 — One Company at a Time**

Each company runs in its **own isolated LLM session** (~35k tokens max vs. 200k limit).
The session reads at most 2 filings (1 × 10-K + 1 × 10-Q) and produces three compact files:

| File | Purpose | Size |
|------|---------|------|
| `{TICKER}_facts_latest.json` | Structured KPIs + citations | ~2–5k tokens |
| `{TICKER}_brief_latest.md` | What changed, management tone, AI capex, risks | 800–1500 tokens |
| `{TICKER}_quote_bank.json` | Top 5–10 verbatim management quotes | ~1–2k tokens |

**Agent 3 — Compact Inputs Only**

Agent 3 reads **only** the compact summary files — never raw filings. Its full context
for N companies is predictable and small:

```
N × (facts ~3k + brief ~1.2k + quotes ~1.5k) + system + output
= 5 companies × 5.7k = ~28k tokens of inputs
```

When a specific citation is needed, `search_excerpts(ticker, "keywords")` retrieves
only the matching paragraphs (~1–3k tokens), not the entire filing.

---

## Observability

Arize Phoenix runs locally and auto-instruments all Claude API calls:

```
http://localhost:6006
```

View per-agent traces, token usage per company session, tool calls, and thinking budgets.

---

## LLM Provider Configuration

Set `LLM_PROVIDER` in `.env` to switch providers with no code changes:

| Provider | `LLM_PROVIDER` | Notes |
|----------|---------------|-------|
| Anthropic Claude | `anthropic` | Supports extended thinking. Set `ANTHROPIC_API_KEY`. |
| OpenAI | `openai` | Set `OPENAI_BASE_URL=https://api.openai.com/v1`, `OPENAI_API_KEY`, `OPENAI_MODEL`. |
| Google Gemini | `openai` | Set `OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`, `OPENAI_API_KEY` (Gemini key), `OPENAI_MODEL=gemini-2.0-flash`. |
| Local server | `openai` | Set `OPENAI_BASE_URL=http://127.0.0.1:17777/v1`, `OPENAI_MODEL=<model-id>`. |

See `.env.example` for a full template.

---

## Key Design Principles

- **Cache-first**: Agent 1 never re-downloads filings < 24 months old
- **No fabrication**: All agents have explicit guardrails against hallucinated data
- **No internet in analysis**: Agents 2–4 read only from local files
- **Isolated sessions**: Agent 2 runs one LLM session per company to prevent context overflow
- **Compact intermediates**: Agent 3 reads only the pre-extracted summaries (facts + brief + quotes)
- **Targeted retrieval**: `search_excerpts` provides citation support without full filing ingestion
- **Adaptive thinking**: Agents 2 and 3 use extended thinking (Anthropic only) for deeper reasoning
- **Configurable LLM**: Switch between Anthropic, OpenAI, Gemini, or any local server via `.env`
- **Observability**: Every API call is traced via Arize Phoenix

---

## Architecture Details

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design and data flow diagram.
