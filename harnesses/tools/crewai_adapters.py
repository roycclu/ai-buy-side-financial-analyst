"""CrewAI tool adapters — wraps existing Python tools as CrewAI BaseTool subclasses.

Each tool stores `project` as a Pydantic field so that agents can be constructed
with project-aware tools via `ToolClass(project=project)`.

Usage:
    tools = create_crewai_tools(project="AI_Capex_2025", phase="research")
"""

import json
from typing import Type

from pydantic import BaseModel, Field


# ── Input schemas ─────────────────────────────────────────────────────────────

class _CheckCacheInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g. 'MSFT')")
    filing_type: str = Field(default="10-K", description="Filing type: '10-K' or '10-Q'")

class _LookupCikInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str = Field(default="", description="Company name (optional, improves lookup accuracy)")

class _SearchEdgarInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    cik: str = Field(..., description="SEC CIK number (from lookup_cik)")
    filing_type: str = Field(default="10-K", description="Filing type: '10-K' or '10-Q'")
    months_back: int = Field(default=24, description="How many months back to search")

class _DownloadFilingInput(BaseModel):
    url: str = Field(..., description="Filing document URL from search_sec_edgar results")
    ticker: str = Field(..., description="Stock ticker symbol")
    filing_type: str = Field(..., description="Filing type: '10-K' or '10-Q'")
    filename: str = Field(..., description="Filename to save as (e.g. 'msft-10K-20240630.htm')")

class _ListFilesInput(BaseModel):
    directory: str = Field(..., description="Absolute or project-relative directory path to list")

class _RunExtractionInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol to extract data for")

class _GetFinancialStatementsInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")

class _GetCompanyBriefInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")

class _GetQuoteBankInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")

class _SearchFilingsInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    query: str = Field(..., description="Keywords to search for (space-separated)")

class _ComputeMultiplesInput(BaseModel):
    tickers: list = Field(..., description="List of ticker symbols to compute multiples for")

class _RunDCFInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    growth_rate: float = Field(default=0.10, description="FCF growth rate (0.10 = 10%)")
    discount_rate: float = Field(default=0.10, description="WACC / discount rate")
    terminal_growth: float = Field(default=0.03, description="Terminal growth rate")
    years: int = Field(default=5, description="DCF projection horizon in years")

class _SaveAnalystReportInput(BaseModel):
    company: str = Field(..., description="Company ticker or name (used in filename)")
    content: str = Field(..., description="Markdown content of the analyst report")

class _SaveSectorReportInput(BaseModel):
    content: str = Field(..., description="Markdown content of the sector report")

class _CreateBarChartInput(BaseModel):
    title: str = Field(..., description="Chart title")
    labels: list = Field(..., description="X-axis labels")
    values: list = Field(..., description="Bar values")
    filename: str = Field(..., description="Output filename (without .png)")
    y_label: str = Field(default="", description="Y-axis label")
    x_label: str = Field(default="", description="X-axis label")

class _CreateLineChartInput(BaseModel):
    title: str = Field(..., description="Chart title")
    x_labels: list = Field(..., description="X-axis labels (time periods)")
    series_dict: dict = Field(..., description="Series data: {series_name: [values]}")
    filename: str = Field(..., description="Output filename (without .png)")
    y_label: str = Field(default="", description="Y-axis label")
    x_label: str = Field(default="", description="X-axis label")

class _CreateComparisonChartInput(BaseModel):
    title: str = Field(..., description="Chart title")
    companies: list = Field(..., description="List of company names/tickers")
    metric_name: str = Field(..., description="Name of the metric being compared")
    values_dict: dict = Field(..., description="Values per company: {company: value}")
    filename: str = Field(..., description="Output filename (without .png)")
    y_label: str = Field(default="", description="Y-axis label")


# ── Tool class factories ───────────────────────────────────────────────────────

def _make_tools(project: str) -> dict:
    """Build all tool instances bound to the given project."""
    from crewai.tools import BaseTool

    class CheckLocalCacheTool(BaseTool):
        name: str = "check_local_cache"
        description: str = (
            "Check whether SEC filings are already cached locally for a given ticker "
            "and filing type. Returns cache status and list of cached files."
        )
        args_schema: Type[BaseModel] = _CheckCacheInput
        project: str = ""
        def _run(self, ticker: str, filing_type: str = "10-K") -> str:
            from tools.edgar_tools import check_local_cache
            return json.dumps(check_local_cache(ticker, filing_type, self.project))

    class LookupCikTool(BaseTool):
        name: str = "lookup_cik"
        description: str = "Look up the SEC CIK number for a company ticker via EDGAR."
        args_schema: Type[BaseModel] = _LookupCikInput
        def _run(self, ticker: str, company_name: str = "") -> str:
            from tools.edgar_tools import lookup_cik
            return json.dumps(lookup_cik(ticker, company_name))

    class SearchSecEdgarTool(BaseTool):
        name: str = "search_sec_edgar"
        description: str = (
            "Search SEC EDGAR submissions for recent filings of a given type. "
            "Requires the CIK from lookup_cik. Returns filing URLs and metadata."
        )
        args_schema: Type[BaseModel] = _SearchEdgarInput
        def _run(self, ticker: str, cik: str, filing_type: str = "10-K", months_back: int = 24) -> str:
            from tools.edgar_tools import search_sec_edgar
            return json.dumps(search_sec_edgar(ticker, cik, filing_type, months_back))

    class DownloadFilingTool(BaseTool):
        name: str = "download_filing"
        description: str = "Download a SEC filing document to the local cache."
        args_schema: Type[BaseModel] = _DownloadFilingInput
        project: str = ""
        def _run(self, url: str, ticker: str, filing_type: str, filename: str) -> str:
            from tools.edgar_tools import download_filing
            return json.dumps(download_filing(url, ticker, filing_type, filename, self.project))

    class ListFilesTool(BaseTool):
        name: str = "list_files"
        description: str = "List files in a directory. Useful for checking what filings are cached."
        args_schema: Type[BaseModel] = _ListFilesInput
        def _run(self, directory: str) -> str:
            from tools.file_tools import list_files
            return json.dumps(list_files(directory))

    class RunExtractionTool(BaseTool):
        name: str = "run_company_data_extraction"
        description: str = (
            "Extract structured financial data from raw SEC filings for a single company. "
            "Runs an isolated LLM session and saves facts JSON, company brief, and quote bank. "
            "Skips automatically if data already exists."
        )
        args_schema: Type[BaseModel] = _RunExtractionInput
        project: str = ""
        def _run(self, ticker: str) -> str:
            from tools.financial_analysis import run_company_data_extraction
            return json.dumps(run_company_data_extraction(ticker, self.project))

    class GetFinancialStatementsTool(BaseTool):
        name: str = "get_financial_statements"
        description: str = "Load the full KPI table (income statement, balance sheet, cash flow) from extracted facts JSON."
        args_schema: Type[BaseModel] = _GetFinancialStatementsInput
        project: str = ""
        def _run(self, ticker: str) -> str:
            from tools.financial_analysis import get_financial_statements
            return json.dumps(get_financial_statements(ticker, self.project))

    class GetCompanyBriefTool(BaseTool):
        name: str = "get_company_brief"
        description: str = "Load the human-readable company brief (markdown summary) extracted from SEC filings."
        args_schema: Type[BaseModel] = _GetCompanyBriefInput
        project: str = ""
        def _run(self, ticker: str) -> str:
            from tools.financial_analysis import get_company_brief
            return json.dumps(get_company_brief(ticker, self.project))

    class GetQuoteBankTool(BaseTool):
        name: str = "get_quote_bank"
        description: str = "Load the management quote bank (key executive quotes from earnings calls and filings)."
        args_schema: Type[BaseModel] = _GetQuoteBankInput
        project: str = ""
        def _run(self, ticker: str) -> str:
            from tools.financial_analysis import get_quote_bank
            return json.dumps(get_quote_bank(ticker, self.project))

    class SearchFilingsTool(BaseTool):
        name: str = "search_filings_by_query"
        description: str = "Search local SEC filings for paragraphs matching a keyword query. Returns relevant excerpts."
        args_schema: Type[BaseModel] = _SearchFilingsInput
        project: str = ""
        def _run(self, ticker: str, query: str) -> str:
            from tools.financial_analysis import search_filings_by_query
            return json.dumps(search_filings_by_query(ticker, query, self.project))

    class ComputeMultiplesTool(BaseTool):
        name: str = "compute_multiples"
        description: str = "Compute valuation multiples (P/E, EV/EBITDA, P/FCF, etc.) from extracted facts data."
        args_schema: Type[BaseModel] = _ComputeMultiplesInput
        project: str = ""
        def _run(self, tickers: list) -> str:
            from tools.financial_analysis import compute_multiples
            return json.dumps(compute_multiples(tickers, self.project))

    class RunDCFTool(BaseTool):
        name: str = "run_dcf"
        description: str = "Run a simple DCF valuation using extracted FCF data from the facts JSON."
        args_schema: Type[BaseModel] = _RunDCFInput
        project: str = ""
        def _run(self, ticker: str, growth_rate: float = 0.10, discount_rate: float = 0.10,
                 terminal_growth: float = 0.03, years: int = 5) -> str:
            from tools.financial_analysis import run_dcf
            return json.dumps(run_dcf(ticker, self.project, growth_rate, discount_rate, terminal_growth, years))

    class SaveAnalystReportTool(BaseTool):
        name: str = "save_analyst_report"
        description: str = "Save an individual company analyst report to the Financial Analyses directory."
        args_schema: Type[BaseModel] = _SaveAnalystReportInput
        project: str = ""
        def _run(self, company: str, content: str) -> str:
            from tools.file_tools import save_analyst_report
            return json.dumps(save_analyst_report(self.project, company, content))

    class SaveSectorReportTool(BaseTool):
        name: str = "save_sector_report"
        description: str = "Save the cross-company sector synthesis report."
        args_schema: Type[BaseModel] = _SaveSectorReportInput
        project: str = ""
        def _run(self, content: str) -> str:
            from tools.file_tools import save_sector_report
            return json.dumps(save_sector_report(self.project, content))

    class CreateBarChartTool(BaseTool):
        name: str = "create_bar_chart"
        description: str = "Create a bar chart PNG comparing values across categories."
        args_schema: Type[BaseModel] = _CreateBarChartInput
        project: str = ""
        def _run(self, title: str, labels: list, values: list, filename: str,
                 y_label: str = "", x_label: str = "") -> str:
            from tools.visualization_tools import create_bar_chart
            return json.dumps(create_bar_chart(title, labels, values, self.project, filename,
                                               y_label=y_label, x_label=x_label))

    class CreateLineChartTool(BaseTool):
        name: str = "create_line_chart"
        description: str = "Create a multi-series line chart PNG for time-series financial data."
        args_schema: Type[BaseModel] = _CreateLineChartInput
        project: str = ""
        def _run(self, title: str, x_labels: list, series_dict: dict, filename: str,
                 y_label: str = "", x_label: str = "") -> str:
            from tools.visualization_tools import create_line_chart
            return json.dumps(create_line_chart(title, x_labels, series_dict, self.project, filename,
                                                y_label=y_label, x_label=x_label))

    class CreateComparisonChartTool(BaseTool):
        name: str = "create_comparison_chart"
        description: str = "Create a grouped comparison bar chart comparing a metric across multiple companies."
        args_schema: Type[BaseModel] = _CreateComparisonChartInput
        project: str = ""
        def _run(self, title: str, companies: list, metric_name: str, values_dict: dict,
                 filename: str, y_label: str = "") -> str:
            from tools.visualization_tools import create_comparison_chart
            return json.dumps(create_comparison_chart(title, companies, metric_name, values_dict,
                                                       self.project, filename, y_label=y_label))

    return {
        "check_local_cache": CheckLocalCacheTool(project=project),
        "lookup_cik": LookupCikTool(),
        "search_sec_edgar": SearchSecEdgarTool(),
        "download_filing": DownloadFilingTool(project=project),
        "list_files": ListFilesTool(),
        "run_company_data_extraction": RunExtractionTool(project=project),
        "get_financial_statements": GetFinancialStatementsTool(project=project),
        "get_company_brief": GetCompanyBriefTool(project=project),
        "get_quote_bank": GetQuoteBankTool(project=project),
        "search_filings_by_query": SearchFilingsTool(project=project),
        "compute_multiples": ComputeMultiplesTool(project=project),
        "run_dcf": RunDCFTool(project=project),
        "save_analyst_report": SaveAnalystReportTool(project=project),
        "save_sector_report": SaveSectorReportTool(project=project),
        "create_bar_chart": CreateBarChartTool(project=project),
        "create_line_chart": CreateLineChartTool(project=project),
        "create_comparison_chart": CreateComparisonChartTool(project=project),
    }


# ── Phase-specific tool sets ──────────────────────────────────────────────────

_PHASE_TOOL_NAMES = {
    "research":   ["check_local_cache", "lookup_cik", "search_sec_edgar", "download_filing", "list_files"],
    "extract":    ["list_files", "run_company_data_extraction"],
    "analyze":    ["get_financial_statements", "get_company_brief", "get_quote_bank",
                   "search_filings_by_query", "compute_multiples", "run_dcf",
                   "save_analyst_report", "save_sector_report"],
    "visualize":  ["get_financial_statements", "create_bar_chart", "create_line_chart", "create_comparison_chart"],
}


def create_crewai_tools(project: str, phase: str = "all") -> list:
    """Return a list of CrewAI tool objects for the given phase and project.

    Args:
        project: Project name (tools are pre-bound to this project).
        phase: One of "research", "extract", "analyze", "visualize", or "all".

    Returns:
        List of BaseTool instances ready for use in a CrewAI Agent.
    """
    all_tools = _make_tools(project)
    if phase == "all":
        return list(all_tools.values())
    names = _PHASE_TOOL_NAMES.get(phase, [])
    return [all_tools[n] for n in names if n in all_tools]
