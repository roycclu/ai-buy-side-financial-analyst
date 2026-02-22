# Buy-Side Financial Analyst Agent Team — Architecture

## Folder Structure

```
Buy Side Financial Analyst/
├── main.py                             ← Entry point → ProjectManager
├── config.py                           ← Paths, model, API endpoints
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── agent0_project_manager.py       ← CLI UX + orchestration launcher
│   ├── agent1_research.py              ← EDGAR fetcher (cache-first)
│   ├── agent2_analyst.py              ← Financial data extractor
│   ├── agent3_lead.py                  ← Investment thesis + sector report
│   └── agent4_visualization.py         ← Chart generator (matplotlib)
│
├── orchestration/
│   └── workflow.py                     ← Sequential pipeline (1→2→3→4)
│
├── tools/
│   ├── __init__.py                     ← Registry + execute_tool dispatcher
│   ├── edgar_tools.py                  ← CIK lookup, cache check, EDGAR API
│   ├── file_tools.py                   ← read_file, save_file, domain savers
│   └── visualization_tools.py          ← Bar, line, comparison charts
│
├── utils/
│   ├── prompts.py                      ← All 5 system prompts + message builders
│   └── file_manager.py                 ← Path helpers, directory scaffolding
│
├── observability/
│   └── arize_logger.py                 ← Arize Phoenix auto-instrumentation
│
├── projects/
│   └── projects.json                   ← Project registry
│
├── Financial Files/                    ← Cache: raw SEC filings per company
│   └── {TICKER}/
│       ├── 10K/
│       ├── 10Q/
│       └── ...
│
├── Financial Data/                     ← Cache: extracted metrics (Markdown)
│   └── {Company}_{TICKER}_{date}.md
│
└── Financial Analyses/                 ← Per-project analysis outputs
    └── {project_name}/
        ├── analyst_reports/
        │   └── {company}_analyst_report.md
        ├── sector_reports/
        │   └── sector_report.md
        └── visualizations/
            └── *.png
```

---

## Agent Roles

| Agent | Name | Role | Thinking | Output |
|-------|------|------|----------|--------|
| 0 | Project Manager | CLI UX, project setup, workflow launch | — | `projects.json` |
| 1 | Research Agent | EDGAR filing fetcher, cache-first | Off | `Financial Files/` |
| 2 | Analyst Agent | Financial metric extractor | Enabled (5k tokens) | `Financial Data/` |
| 3 | Lead Analyst | Investment thesis + sector report | Enabled (8k tokens) | `Financial Analyses/{project}/` |
| 4 | Visualization Agent | Chart generation from viz specs | Off | `visualizations/*.png` |

---

## Operating Principles

### THINK → PLAN → EXECUTE → STORE → LOG

1. **Think first** — Agents 2 and 3 use extended thinking (`interleaved-thinking-2025-05-14` beta) to reason deeply before generating output.
2. **Cache-first** — Agent 1 always calls `check_local_cache` before any EDGAR network call. Filings < 24 months old are reused.
3. **No fabrication** — All system prompts include explicit guardrails: "Do NOT fabricate financial metrics."
4. **Designated storage** — Each agent writes only to its assigned directory:
   - Agent 1 → `Financial Files/`
   - Agent 2 → `Financial Data/`
   - Agent 3 → `Financial Analyses/{project}/analyst_reports/` and `sector_reports/`
   - Agent 4 → `Financial Analyses/{project}/visualizations/`
5. **No internet in analysis** — Agents 2, 3, and 4 have no web-access tools. All data comes from local files.
6. **Observability** — Arize Phoenix auto-instruments all Anthropic API calls via `AnthropicInstrumentor`. Dashboard at `http://localhost:6006`.

---

## Data Flow

```
User Input (Agent 0)
       │
       ▼
Agent 1: SEC EDGAR → Financial Files/{TICKER}/10K/, 10Q/
       │
       ▼
Agent 2: Financial Files/ → Financial Data/{Company}_{TICKER}_{date}.md
       │
       ▼
Agent 3: Financial Data/ → analyst_reports/{company}_analyst_report.md
                        → sector_reports/sector_report.md
                        → viz_specs JSON (passed to Agent 4)
       │
       ▼
Agent 4: Financial Data/ + viz_specs → visualizations/*.png
```

---

## Caching Strategy

| Layer | Location | Key | Freshness |
|-------|----------|-----|-----------|
| Raw filings | `Financial Files/{TICKER}/{type}/` | Ticker + filing type | 24 months |
| Extracted metrics | `Financial Data/` | `{Company}_{TICKER}_{date}.md` | Per-run |
| Analyst reports | `Financial Analyses/{project}/` | Project + company | Per-run |

Agent 1 reads cache freshness via `check_local_cache` before every EDGAR call.
If cache is fresh, it skips all network activity for that filing type.

---

## Model Configuration

```python
MODEL = "claude-opus-4-6"
MAX_TOKENS = 8192
MAX_AGENT_TURNS = 25
```

Agents 2 and 3 use `thinking={"type": "enabled", "budget_tokens": N}` with
the `interleaved-thinking-2025-05-14` beta for deeper analytical reasoning.

---

## Observability

Arize Phoenix is launched at workflow start via `setup_observability()`.
The `AnthropicInstrumentor` automatically wraps all `client.messages.create` calls,
capturing:
- Input/output tokens
- Tool calls and results
- Thinking tokens
- Latency per agent turn

View traces at: **http://localhost:6006**
