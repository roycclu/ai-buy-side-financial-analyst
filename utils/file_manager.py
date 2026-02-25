"""Path helpers and directory scaffolding utilities."""

import math
import os
from datetime import datetime

from config import (
    BASE_DIR,
    FINANCIAL_FILES_DIR,
    FINANCIAL_DATA_DIR,
    FINANCIAL_ANALYSES_DIR,
)


def ensure_dir(path: str) -> str:
    """Create directory (and parents) if it doesn't exist. Returns the path."""
    os.makedirs(path, exist_ok=True)
    return path


def get_financial_data_path(company: str, ticker: str, project: str) -> str:
    """Build the expected Financial Data filepath for a company.

    Pattern: Financial Data/{project}/{Company}_{TICKER}_{YYYY-MM-DD}.md
    Returns the most recent matching file if one exists, otherwise the new path.
    """
    ticker_upper = ticker.upper().strip()
    company_safe = company.replace(" ", "_").replace("/", "_")
    prefix = f"{company_safe}_{ticker_upper}_"
    project_data_dir = os.path.join(FINANCIAL_DATA_DIR, project)

    # Look for an existing data file
    if os.path.isdir(project_data_dir):
        candidates = [
            f for f in os.listdir(project_data_dir)
            if f.startswith(prefix) and f.endswith(".md")
        ]
        if candidates:
            candidates.sort(reverse=True)  # Most recent first (lexicographic on YYYY-MM-DD)
            return os.path.join(project_data_dir, candidates[0])

    # Return a new path with today's date
    date_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(project_data_dir, f"{prefix}{date_str}.md")


def get_ticker_files_dir(ticker: str, filing_type: str, project: str) -> str:
    """Return (and create) the cache dir for a ticker / filing type combination."""
    filing_type_safe = filing_type.replace("-", "").replace("/", "_")
    path = os.path.join(FINANCIAL_FILES_DIR, project, ticker.upper(), filing_type_safe)
    return ensure_dir(path)


def get_project_dir(project: str) -> str:
    """Return (and create) the top-level analysis directory for a project."""
    return ensure_dir(os.path.join(FINANCIAL_ANALYSES_DIR, project))


def get_analyst_report_dir(project: str) -> str:
    return ensure_dir(os.path.join(FINANCIAL_ANALYSES_DIR, project, "analyst_reports"))


def get_sector_report_dir(project: str) -> str:
    return ensure_dir(os.path.join(FINANCIAL_ANALYSES_DIR, project, "sector_reports"))


def get_visualization_dir(project: str) -> str:
    return ensure_dir(os.path.join(FINANCIAL_ANALYSES_DIR, project, "visualizations"))


def scaffold_project_dirs(project: str) -> dict:
    """Create all subdirectories needed for a project.

    Returns a dict of {dir_name: path} for all created directories.
    """
    dirs = {
        "project": get_project_dir(project),
        "analyst_reports": get_analyst_report_dir(project),
        "sector_reports": get_sector_report_dir(project),
        "visualizations": get_visualization_dir(project),
        "financial_data": ensure_dir(os.path.join(FINANCIAL_DATA_DIR, project)),
        "financial_files": ensure_dir(os.path.join(FINANCIAL_FILES_DIR, project)),
    }
    return dirs


def _safe_float(value) -> float | None:
    """Safely convert a value to float, returning None if not possible."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None
