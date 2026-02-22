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
    LIST_FILES_TOOL,
    READ_FILE_TOOL,
    SAVE_FILE_TOOL,
    SAVE_FINANCIAL_DATA_TOOL,
    SAVE_ANALYST_REPORT_TOOL,
    SAVE_SECTOR_REPORT_TOOL,
)

# ── Per-agent tool sets (Agents 1–3 have no matplotlib dependency) ────────────

AGENT1_TOOL_DEFINITIONS = [
    CHECK_CACHE_TOOL,
    LOOKUP_CIK_TOOL,
    SEARCH_EDGAR_TOOL,
    DOWNLOAD_FILING_TOOL,
    LIST_FILES_TOOL,
]

AGENT2_TOOL_DEFINITIONS = [
    LIST_FILES_TOOL,
    READ_FILE_TOOL,
    SAVE_FINANCIAL_DATA_TOOL,
]

AGENT3_TOOL_DEFINITIONS = [
    READ_FILE_TOOL,
    LIST_FILES_TOOL,
    SAVE_ANALYST_REPORT_TOOL,
    SAVE_SECTOR_REPORT_TOOL,
]


def get_agent4_tool_definitions() -> list:
    """Return Agent 4 tool definitions (imports visualization_tools lazily)."""
    from tools.visualization_tools import (
        CREATE_BAR_CHART_TOOL,
        CREATE_LINE_CHART_TOOL,
        CREATE_COMPARISON_CHART_TOOL,
    )
    return [READ_FILE_TOOL, CREATE_BAR_CHART_TOOL, CREATE_LINE_CHART_TOOL, CREATE_COMPARISON_CHART_TOOL]


# ── Function dispatch maps ───────────────────────────────────────────────────

AGENT1_FUNCTIONS = {
    "check_local_cache": check_local_cache,
    "lookup_cik": lookup_cik,
    "search_sec_edgar": search_sec_edgar,
    "download_filing": download_filing,
    "list_files": list_files,
}

AGENT2_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
    "save_financial_data": save_financial_data,
}

AGENT3_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
    "save_analyst_report": save_analyst_report,
    "save_sector_report": save_sector_report,
}


def get_agent4_functions() -> dict:
    """Return Agent 4 function dispatch map (imports visualization_tools lazily)."""
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
