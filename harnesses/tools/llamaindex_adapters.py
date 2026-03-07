"""LlamaIndex tool adapters — wraps existing Python tools as FunctionTool objects.

Each tool function is wrapped with functools.partial to pre-bind the `project`
argument, keeping individual tool signatures clean for the ReActAgent.

Usage:
    tools = create_llamaindex_tools(project="AI_Capex_2025", phase="research")
    tools = create_llamaindex_tools(project="AI_Capex_2025", phase="analyze", rag_engine=engine)
"""

import json
from functools import partial


# ── Pure tool functions (pre-binding targets) ─────────────────────────────────

def _check_local_cache(ticker: str, filing_type: str = "10-K", *, project: str) -> str:
    """Check if SEC filings are cached locally for the given ticker."""
    from tools.edgar_tools import check_local_cache
    return json.dumps(check_local_cache(ticker, filing_type, project))


def _lookup_cik(ticker: str, company_name: str = "") -> str:
    """Look up the SEC CIK number for a company ticker."""
    from tools.edgar_tools import lookup_cik
    return json.dumps(lookup_cik(ticker, company_name))


def _search_sec_edgar(ticker: str, cik: str, filing_type: str = "10-K", months_back: int = 24) -> str:
    """Search SEC EDGAR submissions for recent filings."""
    from tools.edgar_tools import search_sec_edgar
    return json.dumps(search_sec_edgar(ticker, cik, filing_type, months_back))


def _download_filing(url: str, ticker: str, filing_type: str, filename: str, *, project: str) -> str:
    """Download a SEC filing document to the local cache."""
    from tools.edgar_tools import download_filing
    return json.dumps(download_filing(url, ticker, filing_type, filename, project))


def _list_files(directory: str) -> str:
    """List files in a directory."""
    from tools.file_tools import list_files
    return json.dumps(list_files(directory))


def _run_company_data_extraction(ticker: str, *, project: str) -> str:
    """Extract structured financial data for a single company."""
    from tools.financial_analysis import run_company_data_extraction
    return json.dumps(run_company_data_extraction(ticker, project))


def _get_financial_statements(ticker: str, *, project: str) -> str:
    """Load full KPI table from extracted facts JSON."""
    from tools.financial_analysis import get_financial_statements
    return json.dumps(get_financial_statements(ticker, project))


def _get_company_brief(ticker: str, *, project: str) -> str:
    """Load the human-readable company brief markdown."""
    from tools.financial_analysis import get_company_brief
    return json.dumps(get_company_brief(ticker, project))


def _get_quote_bank(ticker: str, *, project: str) -> str:
    """Load management quotes from the quote bank JSON."""
    from tools.financial_analysis import get_quote_bank
    return json.dumps(get_quote_bank(ticker, project))


def _search_filings_by_query(ticker: str, query: str, *, project: str) -> str:
    """Search local SEC filings for paragraphs matching a keyword query."""
    from tools.financial_analysis import search_filings_by_query
    return json.dumps(search_filings_by_query(ticker, query, project))


def _compute_multiples(tickers: list, *, project: str) -> str:
    """Compute valuation multiples from extracted facts data."""
    from tools.financial_analysis import compute_multiples
    return json.dumps(compute_multiples(tickers, project))


def _run_dcf(ticker: str, growth_rate: float = 0.10, discount_rate: float = 0.10,
             terminal_growth: float = 0.03, years: int = 5, *, project: str) -> str:
    """Run a DCF valuation using extracted FCF data."""
    from tools.financial_analysis import run_dcf
    return json.dumps(run_dcf(ticker, project, growth_rate, discount_rate, terminal_growth, years))


def _save_analyst_report(company: str, content: str, *, project: str) -> str:
    """Save an individual company analyst report."""
    from tools.file_tools import save_analyst_report
    return json.dumps(save_analyst_report(project, company, content))


def _save_sector_report(content: str, *, project: str) -> str:
    """Save the cross-company sector synthesis report."""
    from tools.file_tools import save_sector_report
    return json.dumps(save_sector_report(project, content))


def _create_bar_chart(title: str, labels: list, values: list, filename: str,
                      y_label: str = "", x_label: str = "", *, project: str) -> str:
    """Create a bar chart PNG."""
    from tools.visualization_tools import create_bar_chart
    return json.dumps(create_bar_chart(title, labels, values, project, filename,
                                       y_label=y_label, x_label=x_label))


def _create_line_chart(title: str, x_labels: list, series_dict: dict, filename: str,
                       y_label: str = "", x_label: str = "", *, project: str) -> str:
    """Create a multi-series line chart PNG."""
    from tools.visualization_tools import create_line_chart
    return json.dumps(create_line_chart(title, x_labels, series_dict, project, filename,
                                        y_label=y_label, x_label=x_label))


def _create_comparison_chart(title: str, companies: list, metric_name: str, values_dict: dict,
                              filename: str, y_label: str = "", *, project: str) -> str:
    """Create a grouped comparison bar chart."""
    from tools.visualization_tools import create_comparison_chart
    return json.dumps(create_comparison_chart(title, companies, metric_name, values_dict,
                                               project, filename, y_label=y_label))


# ── Tool metadata ─────────────────────────────────────────────────────────────

_TOOL_SPECS = [
    # (name, fn, description, needs_project)
    ("check_local_cache",          _check_local_cache,
     "Check if SEC filings are cached locally for a ticker.",                     True),
    ("lookup_cik",                 _lookup_cik,
     "Look up the SEC CIK number for a company ticker.",                           False),
    ("search_sec_edgar",           _search_sec_edgar,
     "Search SEC EDGAR for recent filings. Requires CIK from lookup_cik.",        False),
    ("download_filing",            _download_filing,
     "Download a SEC filing document to the local cache.",                         True),
    ("list_files",                 _list_files,
     "List files in a directory.",                                                 False),
    ("run_company_data_extraction", _run_company_data_extraction,
     "Extract structured financial data (facts, brief, quotes) for one company.", True),
    ("get_financial_statements",   _get_financial_statements,
     "Load full KPI table from the extracted facts JSON.",                         True),
    ("get_company_brief",          _get_company_brief,
     "Load the human-readable company brief markdown.",                            True),
    ("get_quote_bank",             _get_quote_bank,
     "Load management quotes from the extracted quote bank.",                      True),
    ("search_filings_by_query",    _search_filings_by_query,
     "Search local SEC filings for paragraphs matching a keyword query.",          True),
    ("compute_multiples",          _compute_multiples,
     "Compute valuation multiples (P/E, EV/EBITDA, P/FCF) from facts data.",      True),
    ("run_dcf",                    _run_dcf,
     "Run a 5-year DCF valuation using extracted FCF data.",                       True),
    ("save_analyst_report",        _save_analyst_report,
     "Save an individual company analyst report to disk.",                         True),
    ("save_sector_report",         _save_sector_report,
     "Save the cross-company sector synthesis report.",                            True),
    ("create_bar_chart",           _create_bar_chart,
     "Create a bar chart PNG.",                                                    True),
    ("create_line_chart",          _create_line_chart,
     "Create a multi-series line chart PNG.",                                      True),
    ("create_comparison_chart",    _create_comparison_chart,
     "Create a grouped comparison bar chart across companies.",                    True),
]

_PHASE_TOOL_NAMES = {
    "research":  ["check_local_cache", "lookup_cik", "search_sec_edgar", "download_filing", "list_files"],
    "extract":   ["list_files", "run_company_data_extraction"],
    "analyze":   ["get_financial_statements", "get_company_brief", "get_quote_bank",
                  "search_filings_by_query", "compute_multiples", "run_dcf",
                  "save_analyst_report", "save_sector_report"],
    "visualize": ["get_financial_statements", "create_bar_chart", "create_line_chart", "create_comparison_chart"],
}


def create_llamaindex_tools(
    project: str,
    phase: str = "all",
    rag_engine=None,
) -> list:
    """Return a list of LlamaIndex FunctionTool objects for the given phase.

    Args:
        project: Project name (tools are pre-bound to this project).
        phase: One of "research", "extract", "analyze", "visualize", or "all".
        rag_engine: Optional QueryEngine. When provided, prepends a RAG query tool.

    Returns:
        List of FunctionTool instances ready for use in a ReActAgent.
    """
    from llama_index.core.tools import FunctionTool

    names = set(_PHASE_TOOL_NAMES.get(phase, [n for n, *_ in _TOOL_SPECS]) if phase != "all"
                else [n for n, *_ in _TOOL_SPECS])

    tools = []

    # Prepend RAG query tool when provided
    if rag_engine is not None:
        from llama_index.core.tools import QueryEngineTool
        rag_tool = QueryEngineTool.from_defaults(
            query_engine=rag_engine,
            name="query_local_documents",
            description=(
                "Query the local SEC filing documents using natural language. "
                "Use this to check whether filings exist locally and to retrieve specific information. "
                "Example: 'What 10-K filings are available for MSFT?'"
            ),
        )
        tools.append(rag_tool)

    for name, fn, description, needs_project in _TOOL_SPECS:
        if name not in names:
            continue
        bound_fn = partial(fn, project=project) if needs_project else fn
        tool = FunctionTool.from_defaults(
            fn=bound_fn,
            name=name,
            description=description,
        )
        tools.append(tool)

    return tools
