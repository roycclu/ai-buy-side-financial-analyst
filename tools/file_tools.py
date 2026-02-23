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


# ── Compact-output savers (new architecture) ──────────────────────────────────

def save_company_facts(ticker: str, content: str) -> dict:
    """Save structured CompanyFacts JSON for a company.

    Always writes to Financial Data/{TICKER}_facts_latest.json, overwriting any
    previous version so Agent 3 always finds exactly one current file per ticker.

    Args:
        ticker: Stock ticker symbol (e.g. 'MSFT').
        content: JSON string with structured KPIs and citations.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    ticker_upper = ticker.upper().strip()
    filepath = os.path.join(FINANCIAL_DATA_DIR, f"{ticker_upper}_facts_latest.json")
    return save_file(filepath, content)


def save_company_brief(ticker: str, content: str) -> dict:
    """Save human-readable CompanyBrief markdown for a company.

    Always writes to Financial Data/{TICKER}_brief_latest.md (target 800-1500 tokens).

    Args:
        ticker: Stock ticker symbol (e.g. 'MSFT').
        content: Markdown-formatted company brief.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    ticker_upper = ticker.upper().strip()
    filepath = os.path.join(FINANCIAL_DATA_DIR, f"{ticker_upper}_brief_latest.md")
    return save_file(filepath, content)


def save_quote_bank(ticker: str, content: str) -> dict:
    """Save the QuoteBank JSON (top 5-10 verbatim management quotes) for a company.

    Always writes to Financial Data/{TICKER}_quote_bank.json.

    Args:
        ticker: Stock ticker symbol (e.g. 'MSFT').
        content: JSON array of quote objects with 'quote', 'speaker', 'context' fields.

    Returns:
        Dict with 'success' and 'filepath'.
    """
    ticker_upper = ticker.upper().strip()
    filepath = os.path.join(FINANCIAL_DATA_DIR, f"{ticker_upper}_quote_bank.json")
    return save_file(filepath, content)


def search_excerpts(ticker: str, keywords: str, max_chars: int = 8000) -> dict:
    """Search raw filings for a ticker and return relevant text excerpts.

    Finds paragraphs containing ALL the given keywords (case-insensitive).  Useful for
    retrieving specific evidence or citations without loading an entire filing into context.

    Args:
        ticker: Stock ticker symbol (e.g. 'MSFT').
        keywords: Space-separated keywords (all must appear in a paragraph to match).
        max_chars: Maximum total characters to return across all excerpts (default 8000).

    Returns:
        Dict with 'ticker', 'keywords', 'excerpts' list, and 'total_excerpts_found'.
    """
    ticker_upper = ticker.upper().strip()
    ticker_dir = os.path.join(FINANCIAL_FILES_DIR, ticker_upper)

    if not os.path.isdir(ticker_dir):
        return {
            "ticker": ticker_upper,
            "keywords": keywords,
            "excerpts": [],
            "total_excerpts_found": 0,
            "message": f"No filings directory found for {ticker_upper}.",
        }

    kw_list = [k.lower() for k in keywords.split() if k.strip()]
    if not kw_list:
        return {"ticker": ticker_upper, "keywords": keywords, "excerpts": [], "total_excerpts_found": 0}

    excerpts = []
    chars_used = 0

    # Walk filing subdirectories; sort descending so newest files come first
    try:
        subdirs = sorted(os.listdir(ticker_dir))
    except Exception:
        subdirs = []

    for subdir in subdirs:
        subdir_path = os.path.join(ticker_dir, subdir)
        if not os.path.isdir(subdir_path):
            continue
        try:
            fnames = sorted(os.listdir(subdir_path), reverse=True)
        except Exception:
            continue
        for fname in fnames:
            fpath = os.path.join(subdir_path, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    raw = fh.read()
                if fpath.lower().endswith((".htm", ".html")):
                    raw = _strip_html(raw)
                paragraphs = [p.strip() for p in re.split(r"\n{2,}", raw) if len(p.strip()) > 40]
                for para in paragraphs:
                    if all(kw in para.lower() for kw in kw_list):
                        excerpt = para[:500] + "…" if len(para) > 500 else para
                        excerpts.append({"file": os.path.join(subdir, fname), "text": excerpt})
                        chars_used += len(excerpt)
                        if chars_used >= max_chars:
                            break
            except Exception:
                continue
            if chars_used >= max_chars:
                break
        if chars_used >= max_chars:
            break

    return {
        "ticker": ticker_upper,
        "keywords": keywords,
        "excerpts": excerpts[:20],
        "total_excerpts_found": len(excerpts),
    }


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

SAVE_COMPANY_FACTS_TOOL = {
    "name": "save_company_facts",
    "description": (
        "Save structured CompanyFacts JSON for one company to "
        "Financial Data/{TICKER}_facts_latest.json. "
        "Content must be a valid JSON string containing the KPI table and citations. "
        "Always overwrites the previous version so Agent 3 finds exactly one current file."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. 'MSFT')."},
            "content": {"type": "string", "description": "Valid JSON string with structured financial facts."},
        },
        "required": ["ticker", "content"],
    },
}

SAVE_COMPANY_BRIEF_TOOL = {
    "name": "save_company_brief",
    "description": (
        "Save a human-readable CompanyBrief markdown file for one company to "
        "Financial Data/{TICKER}_brief_latest.md. "
        "Target length: 800–1500 tokens. Covers: what changed, management tone, AI/strategic capex, "
        "key risks, analyst flags. Always overwrites the previous version."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. 'MSFT')."},
            "content": {"type": "string", "description": "Markdown-formatted company brief (800–1500 tokens)."},
        },
        "required": ["ticker", "content"],
    },
}

SAVE_QUOTE_BANK_TOOL = {
    "name": "save_quote_bank",
    "description": (
        "Save the QuoteBank JSON (top 5–10 verbatim management quotes) for one company to "
        "Financial Data/{TICKER}_quote_bank.json. "
        "Content must be a JSON array of objects with 'speaker', 'context', 'quote', 'relevance' fields."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. 'MSFT')."},
            "content": {"type": "string", "description": "JSON array of quote objects."},
        },
        "required": ["ticker", "content"],
    },
}

SEARCH_EXCERPTS_TOOL = {
    "name": "search_excerpts",
    "description": (
        "Search raw filings for a ticker and return relevant paragraph-level excerpts matching keywords. "
        "Use this instead of read_file when you need a specific citation or piece of evidence "
        "without loading an entire filing. All keywords must appear in a paragraph to match. "
        "Returns up to 20 excerpts, capped at max_chars total characters."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g. 'MSFT').",
            },
            "keywords": {
                "type": "string",
                "description": "Space-separated keywords — all must appear in a paragraph to match.",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum total characters to return across all excerpts. Default 8000.",
            },
        },
        "required": ["ticker", "keywords"],
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
