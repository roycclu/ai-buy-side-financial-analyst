"""Tool registry for Claude function-calling — Buy-Side Analyst Agent Team."""

import json

from tools.edgar_tools import (
    lookup_cik,
    check_local_cache,
    search_sec_edgar,
    download_filing,
    LOOKUP_CIK_TOOL,
    CHECK_CACHE_TOOL,
    SEARCH_EDGAR_TOOL,
    DOWNLOAD_FILING_TOOL,
)
from tools.file_tools import (
    list_files,
    read_file,
    save_file,
    save_financial_data,
    save_analyst_report,
    save_sector_report,
    save_company_facts,
    save_company_brief,
    save_quote_bank,
    search_excerpts,
    LIST_FILES_TOOL,
    READ_FILE_TOOL,
    SAVE_FILE_TOOL,
    SAVE_FINANCIAL_DATA_TOOL,
    SAVE_ANALYST_REPORT_TOOL,
    SAVE_SECTOR_REPORT_TOOL,
    SAVE_COMPANY_FACTS_TOOL,
    SAVE_COMPANY_BRIEF_TOOL,
    SAVE_QUOTE_BANK_TOOL,
    SEARCH_EXCERPTS_TOOL,
)

# ── Per-phase tool sets ───────────────────────────────────────────────────────

RESEARCH_TOOL_DEFINITIONS = [
    CHECK_CACHE_TOOL,
    LOOKUP_CIK_TOOL,
    SEARCH_EDGAR_TOOL,
    DOWNLOAD_FILING_TOOL,
    LIST_FILES_TOOL,
]

# Extract phase: reads at most 2 raw filings per company, outputs 3 structured sections in
# plain text.  File saving is handled by the orchestrator — NOT by LLM tool calls.
EXTRACT_TOOL_DEFINITIONS = [
    LIST_FILES_TOOL,
    READ_FILE_TOOL,
]

# Analysis phase: reads only compact summary files; uses search_excerpts for targeted citations.
ANALYSIS_TOOL_DEFINITIONS = [
    LIST_FILES_TOOL,
    READ_FILE_TOOL,
    SEARCH_EXCERPTS_TOOL,
    SAVE_ANALYST_REPORT_TOOL,
    SAVE_SECTOR_REPORT_TOOL,
]


def get_viz_tool_definitions() -> list:
    """Return visualization phase tool definitions (imports visualization_tools lazily)."""
    from tools.visualization_tools import (
        CREATE_BAR_CHART_TOOL,
        CREATE_LINE_CHART_TOOL,
        CREATE_COMPARISON_CHART_TOOL,
    )
    return [READ_FILE_TOOL, CREATE_BAR_CHART_TOOL, CREATE_LINE_CHART_TOOL, CREATE_COMPARISON_CHART_TOOL]


# ── Function dispatch maps ────────────────────────────────────────────────────

RESEARCH_FUNCTIONS = {
    "check_local_cache": check_local_cache,
    "lookup_cik": lookup_cik,
    "search_sec_edgar": search_sec_edgar,
    "download_filing": download_filing,
    "list_files": list_files,
}

EXTRACT_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
}

ANALYSIS_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
    "search_excerpts": search_excerpts,
    "save_analyst_report": save_analyst_report,
    "save_sector_report": save_sector_report,
}


def get_viz_functions() -> dict:
    """Return visualization phase function dispatch map (imports visualization_tools lazily)."""
    from tools.visualization_tools import (
        create_bar_chart,
        create_line_chart,
        create_comparison_chart,
    )
    return {
        "read_file": read_file,
        "create_bar_chart": create_bar_chart,
        "create_line_chart": create_line_chart,
        "create_comparison_chart": create_comparison_chart,
    }


def execute_tool(tool_name: str, tool_input: dict, tool_functions: dict) -> str:
    """Execute a tool by name with the given input and return a JSON string.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Dictionary of input parameters.
        tool_functions: Mapping of tool names to Python callables.

    Returns:
        JSON-encoded string with the tool result.
    """
    func = tool_functions.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = func(**tool_input)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": f"Tool execution failed: {str(exc)}"})
