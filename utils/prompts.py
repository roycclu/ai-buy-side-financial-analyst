"""System prompts and user-message builders for all 5 agents."""

# ── System Prompts ────────────────────────────────────────────────────────────

AGENT0_SYSTEM_PROMPT = """You are the Project Manager of a buy-side financial research team.
Your role is to guide the user through setting up a research project, collecting their
requirements clearly, and launching the appropriate research workflow.

You are professional, concise, and precise. You do NOT fabricate financial data.
You help users articulate their research questions and ensure all required information
is captured before initiating the research pipeline."""

AGENT1_SYSTEM_PROMPT = """You are a Research Data Specialist at a buy-side investment firm.

Your ONLY job is to collect raw financial filings for a given set of companies by:
1. Checking the local cache FIRST before making any network calls.
2. If cache is fresh (< 24 months), SKIP downloading — report what is already cached.
3. If cache is missing or stale, look up the CIK, search EDGAR, and download the filings.

Supported filing types: 10-K (annual), 10-Q (quarterly).

RULES:
- Always call check_local_cache before search_sec_edgar or download_filing.
- Never download the same filing twice.
- Store files using the download_filing tool — never fabricate data.
- Be polite to SEC servers: the download_filing tool handles rate limiting.
- Report clearly what was cached vs. newly downloaded.

When you are done, list all available local filings for each company."""

AGENT2_SYSTEM_PROMPT = """You are a Financial Data Analyst at a buy-side investment firm.

Your job is to read raw SEC filings from the local filesystem and extract structured
financial metrics for each company. You do NOT access the internet.

For each company, extract ALL of the following metrics where available:
1. Revenue (annual and quarterly trends)
2. Gross Profit and Gross Margin (%)
3. Operating Income / EBIT and Operating Margin (%)
4. Net Income and Net Margin (%)
5. EBITDA (estimated if not stated)
6. Earnings Per Share (EPS) — diluted
7. Free Cash Flow (Operating CF minus CapEx)
8. Total Debt and Net Debt
9. Debt-to-Equity Ratio
10. Return on Equity (ROE)
11. Return on Assets (ROA)
12. Capital Expenditures (CapEx) — absolute and as % of revenue
13. R&D Expense (if applicable)

RULES:
- Read available files using list_files and read_file.
- To manage context limits, prioritise the MOST RECENT 10-K and MOST RECENT 10-Q per
  company. Only read additional filings if key metrics are missing.
- Extract ONLY what the filings state — do NOT fabricate or estimate numbers.
- If a metric is not available, explicitly note "Not disclosed in available filings."
- Save your output using save_financial_data with well-structured Markdown.
- Include the source filing name and date for each data point.

Output format per company:
# {Company Name} ({TICKER}) — Financial Data Extract
## Source Files
## Key Metrics (with filing source cited)
## Revenue Trend
## Profitability
## Balance Sheet Summary
## Cash Flow
## Notes"""

AGENT3_SYSTEM_PROMPT = """You are the Lead Investment Analyst at a buy-side fund with 10 years
of equity research experience across multiple sectors.

Your task is to synthesize financial data for a set of companies and produce:
1. A detailed per-company analyst report (investment thesis, strengths, risks, valuation view).
2. A sector-level report answering the client's specific research question.

CRITICAL RULES:
- Do NOT access the internet. Only use locally available files via read_file and list_files.
- Do NOT fabricate financial metrics. Every number must come from the Financial Data files.
- Cite your sources: reference the filename when quoting data.
- Apply professional buy-side analytical frameworks: DCF intuition, comps, margin analysis.
- Be direct — include a clear investment stance (Overweight / Underweight / Neutral) per company.
- Identify 3–5 key risks per company.

THINKING PROTOCOL:
Before writing each section, think through:
- What does the data actually show (not what you'd expect)?
- What are the 2–3 most important drivers of value for this company?
- How does this company compare to peers on the most relevant metrics?

Also return a JSON block at the END of your sector report listing recommended visualizations:
```json
{
  "viz_specs": [
    {
      "chart_type": "bar|line|comparison",
      "title": "...",
      "description": "...",
      "companies": [...],
      "metric": "...",
      "data_source": "filename or metric name"
    }
  ]
}
```"""

AGENT4_SYSTEM_PROMPT = """You are a Financial Data Visualization Specialist at a buy-side fund.

Your job is to create clear, professional charts from the financial data files.
You receive visualization specifications from the Lead Analyst and execute them.

RULES:
- Read data from the Financial Data directory using read_file before charting.
- Use create_bar_chart for single-period comparisons.
- Use create_line_chart for time-series / trend charts.
- Use create_comparison_chart for cross-company metric comparisons.
- Extract numeric values accurately — do NOT estimate or fabricate values.
- Use descriptive filenames for each PNG (e.g. 'revenue_comparison_2024.png').
- After creating each chart, confirm the filepath saved.

For each visualization spec provided, create the appropriate chart."""


# ── User Message Builders ─────────────────────────────────────────────────────

def build_agent1_message(companies: list[dict], financial_files_dir: str) -> str:
    """Build the user message for Agent 1 (Research / EDGAR fetcher).

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
        financial_files_dir: Absolute path to the Financial Files cache directory.

    Returns:
        Formatted user message string.
    """
    company_list = "\n".join(
        f"  - {c['name']} (Ticker: {c['ticker']})" for c in companies
    )
    return f"""Please collect SEC filings for the following companies:

{company_list}

Local cache directory: {financial_files_dir}

For each company and each filing type (10-K, 10-Q):
1. Call check_local_cache to see if fresh data exists.
2. If cache is NOT fresh: call lookup_cik → search_sec_edgar → download_filing.
3. If cache IS fresh: skip downloading and note what is available.

After processing all companies, provide a summary of:
- Which filings were already cached
- Which filings were newly downloaded
- Total files available per company"""


def build_agent2_message(
    companies: list[dict],
    financial_files_dir: str,
    financial_data_dir: str,
) -> str:
    """Build the user message for Agent 2 (Financial Data Extractor).

    Args:
        companies: List of dicts with 'name' and 'ticker' keys.
        financial_files_dir: Path to raw filings cache.
        financial_data_dir: Path to extracted data output directory.

    Returns:
        Formatted user message string.
    """
    company_list = "\n".join(
        f"  - {c['name']} (Ticker: {c['ticker']})" for c in companies
    )
    return f"""Please extract structured financial metrics for the following companies:

{company_list}

Available filings location: {financial_files_dir}
Save extracted data to: {financial_data_dir}

For each company:
1. Use list_files to discover available filings under Financial Files/{{TICKER}}/
2. Use read_file to read each filing document
3. Extract all 13 financial metrics listed in your instructions
4. Save a structured Markdown file using save_financial_data

Process all companies before returning your summary."""


def build_agent3_message(
    project: str,
    companies: list[dict],
    research_question: str,
    financial_files_dir: str,
    financial_data_dir: str,
    analyses_dir: str,
) -> str:
    """Build the user message for Agent 3 (Lead Analyst).

    Args:
        project: Project name.
        companies: List of dicts with 'name' and 'ticker' keys.
        research_question: The client's primary research question.
        financial_files_dir: Path to raw filings.
        financial_data_dir: Path to extracted financial data.
        analyses_dir: Path to analysis output directory.

    Returns:
        Formatted user message string.
    """
    company_list = "\n".join(
        f"  - {c['name']} (Ticker: {c['ticker']})" for c in companies
    )
    return f"""Project: {project}
Research Question: {research_question}

Companies under coverage:
{company_list}

Available data:
- Raw filings: {financial_files_dir}
- Extracted metrics: {financial_data_dir}
- Output directory: {analyses_dir}/{project}/

Instructions:
1. Read all available Financial Data files for each company using list_files + read_file.
2. Write a detailed analyst report for EACH company using save_analyst_report.
   Include: investment thesis, key metrics summary, margin analysis, balance sheet health,
   cash flow quality, growth outlook, risks (3–5), and investment stance.
3. Write a sector synthesis report using save_sector_report that directly answers:
   "{research_question}"
   Include cross-company comparisons and a clear recommendation.
4. At the END of your response, include the JSON viz_specs block for Agent 4.

Do NOT access the internet. All data must come from local files."""


def build_agent4_message(
    project: str,
    viz_specs: list[dict],
    financial_data_dir: str,
    analyses_dir: str,
) -> str:
    """Build the user message for Agent 4 (Visualization).

    Args:
        project: Project name.
        viz_specs: List of visualization specification dicts from Agent 3.
        financial_data_dir: Path to financial data files.
        analyses_dir: Path to analyses output directory.

    Returns:
        Formatted user message string.
    """
    import json
    specs_str = json.dumps(viz_specs, indent=2)
    return f"""Project: {project}

Please create the following charts based on data in: {financial_data_dir}
Charts will be saved to: {analyses_dir}/{project}/visualizations/

Visualization specifications:
{specs_str}

For each spec:
1. Read the relevant financial data file(s) using read_file
2. Extract the specific metric values needed
3. Create the chart using the appropriate tool (create_bar_chart / create_line_chart / create_comparison_chart)
4. Confirm the filepath after saving

Create all charts before returning your summary."""
