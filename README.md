# Buy-Side Financial Analyst Agent Team

A production-quality, multi-agent buy-side financial research system powered by
**Claude Opus 4.6** with adaptive thinking and SEC EDGAR data.

## What It Does

Five coordinated AI agents mimic a real research function:

1. **Agent 0 — Project Manager**: CLI interface for project setup and orchestration
2. **Agent 1 — Research Agent**: Fetches SEC EDGAR filings (10-K, 10-Q) with cache-first logic
3. **Agent 2 — Analyst Agent**: Extracts 13 financial metrics from raw filings
4. **Agent 3 — Lead Analyst**: Writes per-company analyst reports and a sector synthesis
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

The system will then:
- Check local filing cache for MSFT and AAPL
- Download any missing 10-K / 10-Q filings from SEC EDGAR
- Extract financial metrics from the filings
- Write analyst reports + a sector report answering your question
- Generate comparison charts

---

## Output Structure

```
Financial Files/
└── MSFT/10K/, MSFT/10Q/, AAPL/10K/, AAPL/10Q/   ← raw filings (cached)

Financial Data/
└── Microsoft_Corporation_MSFT_2025-02-22.md        ← extracted metrics
└── Apple_Inc_AAPL_2025-02-22.md

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

## Observability

Arize Phoenix runs locally and auto-instruments all Claude API calls:

```
http://localhost:6006
```

View per-agent traces, token usage, tool calls, and thinking budgets.

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design, data flow diagram,
and caching strategy.

---

## Key Design Principles

- **Cache-first**: Agent 1 never re-downloads filings < 24 months old
- **No fabrication**: All agents have explicit guardrails against hallucinated data
- **No internet in analysis**: Agents 2–4 read only from local files
- **Adaptive thinking**: Agents 2 and 3 use extended thinking for deeper analysis
- **Observability**: Every API call is traced via Arize Phoenix
