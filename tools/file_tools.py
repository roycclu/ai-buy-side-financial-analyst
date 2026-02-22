"""File I/O tools for reading and writing research artifacts."""

import os
import re
import html as html_module
from datetime import datetime

from config import FINANCIAL_FILES_DIR, FINANCIAL_DATA_DIR, FINANCIAL_ANALYSES_DIR


_MAX_FILE_CHARS = 40_000  # ~10k tokens per file; keeps multi-file sessions under 200k limit


def _strip_html(text: str) -> str:
    """Strip HTML tags and normalise whitespace for SEC filing .htm files."""
    text = html_module.unescape(text)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Generic helpers ───────────────────────────────────────────────────────────

def list_files(directory: str) -> dict:
    """List files and subdirectories in a given directory.

    Args:
        directory: Absolute or relative path to list.

    Returns:
        Dict with 'directory', 'files', 'subdirectories', and 'total_items'.
    """
    try:
        if not os.path.exists(directory):
            return {
                "directory": directory,
                "files": [],
                "subdirectories": [],
                "total_items": 0,
                "message": "Directory does not exist.",
            }
        entries = os.listdir(directory)
        files = []
        subdirs = []
        for entry in sorted(entries):
            full = os.path.join(directory, entry)
            if os.path.isfile(full):
                size = os.path.getsize(full)
                mtime = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d")
                files.append({"name": entry, "path": full, "size_bytes": size, "modified": mtime})
            elif os.path.isdir(full):
                subdirs.append({"name": entry, "path": full})
        return {
            "directory": directory,
            "files": files,
            "subdirectories": subdirs,
            "total_items": len(files) + len(subdirs),
        }
    except Exception as exc:
        return {"directory": directory, "error": str(exc)}


def read_file(filepath: str) -> dict:
    """Read the text content of a file.

    For HTML files (SEC filings) the raw markup is stripped to plain text
    before returning so that context-window usage stays manageable.
    Content is always truncated to _MAX_FILE_CHARS characters.

    Args:
        filepath: Absolute path to the file.

    Returns:
        Dict with 'filepath', 'content', 'size_chars', and 'truncated'.
    """
    try:
        if not os.path.isfile(filepath):
            return {"filepath": filepath, "error": "File not found."}
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        if filepath.lower().endswith((".htm", ".html")):
            content = _strip_html(content)
        truncated = len(content) > _MAX_FILE_CHARS
        if truncated:
            content = content[:_MAX_FILE_CHARS] + f"\n\n[... truncated — {len(content) - _MAX_FILE_CHARS:,} chars omitted ...]"
        return {
            "filepath": filepath,
            "content": content,
            "size_chars": len(content),
            "truncated": truncated,
        }
    except Exception as exc:
        return {"filepath": filepath, "error": str(exc)}


def save_file(filepath: str, content: str) -> dict:
    """Write text content to an arbitrary file path.

    Args:
        filepath: Absolute path to write.
        content: Text content to save.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {"success": True, "filepath": filepath, "size_chars": len(content)}
    except Exception as exc:
        return {"success": False, "filepath": filepath, "error": str(exc)}


# ── Domain-specific savers ────────────────────────────────────────────────────

def save_financial_data(company: str, ticker: str, content: str) -> dict:
    """Save extracted financial metrics to the Financial Data directory.

    Filename pattern: {Company}_{TICKER}_{YYYY-MM-DD}.md

    Args:
        company: Full company name (spaces replaced with underscores).
        ticker: Stock ticker symbol.
        content: Markdown-formatted financial metrics.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    company_safe = company.replace(" ", "_").replace("/", "_")
    ticker_upper = ticker.upper().strip()
    filename = f"{company_safe}_{ticker_upper}_{date_str}.md"
    filepath = os.path.join(FINANCIAL_DATA_DIR, filename)
    return save_file(filepath, content)


def save_analyst_report(project: str, company: str, content: str) -> dict:
    """Save a per-company analyst report to the Financial Analyses directory.

    Args:
        project: Project name (used as subfolder).
        company: Company name (used in filename).
        content: Markdown report content.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    company_safe = company.lower().replace(" ", "_")
    report_dir = os.path.join(FINANCIAL_ANALYSES_DIR, project, "analyst_reports")
    os.makedirs(report_dir, exist_ok=True)
    filepath = os.path.join(report_dir, f"{company_safe}_analyst_report.md")
    return save_file(filepath, content)


def save_sector_report(project: str, content: str) -> dict:
    """Save the sector-level synthesis report.

    Args:
        project: Project name (used as subfolder).
        content: Markdown sector report content.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    report_dir = os.path.join(FINANCIAL_ANALYSES_DIR, project, "sector_reports")
    os.makedirs(report_dir, exist_ok=True)
    filepath = os.path.join(report_dir, "sector_report.md")
    return save_file(filepath, content)


# ── Tool Definitions ──────────────────────────────────────────────────────────

LIST_FILES_TOOL = {
    "name": "list_files",
    "description": (
        "List all files and subdirectories in a given directory path. "
        "Use this to discover what data is available before reading files."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Absolute path to the directory to list.",
            },
        },
        "required": ["directory"],
    },
}

READ_FILE_TOOL = {
    "name": "read_file",
    "description": (
        "Read the text content of a file. HTML files (SEC filings) are automatically "
        "stripped of markup and returned as plain text. Content is capped at 80,000 "
        "characters; a truncation notice is appended when the file is larger. "
        "Focus on the most-recent filing per company to stay within context limits."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Absolute path to the file to read.",
            },
        },
        "required": ["filepath"],
    },
}

SAVE_FILE_TOOL = {
    "name": "save_file",
    "description": "Write text content to an arbitrary file path, creating directories as needed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "filepath": {"type": "string", "description": "Absolute path to write."},
            "content": {"type": "string", "description": "Text content to save."},
        },
        "required": ["filepath", "content"],
    },
}

SAVE_FINANCIAL_DATA_TOOL = {
    "name": "save_financial_data",
    "description": (
        "Save extracted financial metrics for a company to the Financial Data directory. "
        "The file will be named {Company}_{TICKER}_{date}.md automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "description": "Full company name (e.g. 'Microsoft Corporation').",
            },
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g. 'MSFT').",
            },
            "content": {
                "type": "string",
                "description": "Markdown-formatted financial metrics and data.",
            },
        },
        "required": ["company", "ticker", "content"],
    },
}

SAVE_ANALYST_REPORT_TOOL = {
    "name": "save_analyst_report",
    "description": (
        "Save a per-company investment analyst report to the project's analyst_reports folder."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project name (matches the project directory).",
            },
            "company": {
                "type": "string",
                "description": "Company name (used in the filename).",
            },
            "content": {
                "type": "string",
                "description": "Full Markdown analyst report content.",
            },
        },
        "required": ["project", "company", "content"],
    },
}

SAVE_SECTOR_REPORT_TOOL = {
    "name": "save_sector_report",
    "description": (
        "Save the cross-company sector synthesis report to the project's sector_reports folder."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project name (matches the project directory).",
            },
            "content": {
                "type": "string",
                "description": "Full Markdown sector report content.",
            },
        },
        "required": ["project", "content"],
    },
}
