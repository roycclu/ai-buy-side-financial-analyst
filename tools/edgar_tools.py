"""SEC EDGAR tools — CIK lookup, cache check, filing search & download."""

import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

from config import (
    FINANCIAL_FILES_DIR,
    SEC_EDGAR_SUBMISSIONS_URL,
    SEC_EDGAR_ARCHIVES_URL,
    SEC_EDGAR_BROWSE_URL,
    SEC_EDGAR_USER_AGENT,
)

# Filing types the system handles
SUPPORTED_FILING_TYPES = ["10-K", "10-Q", "8-K", "DEF 14A"]

_HEADERS = {
    "User-Agent": SEC_EDGAR_USER_AGENT,
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}


# ── CIK Lookup ───────────────────────────────────────────────────────────────

def lookup_cik(ticker: str, company_name: str = "") -> dict:
    """Dynamically resolve a CIK for a ticker via SEC EDGAR.

    Args:
        ticker: Stock ticker symbol (e.g. "MSFT").
        company_name: Optional company name hint for disambiguation.

    Returns:
        Dict with 'ticker', 'cik', 'company_name' or 'error'.
    """
    ticker = ticker.upper().strip()

    # Try the EDGAR company search API first (fastest)
    try:
        url = "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&dateRange=custom&startdt=2000-01-01&forms=10-K".format(ticker)
        # Use the company tickers JSON which SEC publishes
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(tickers_url, headers=_HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for _idx, entry in data.items():
                if entry.get("ticker", "").upper() == ticker:
                    cik_raw = str(entry["cik_str"]).zfill(10)
                    return {
                        "ticker": ticker,
                        "cik": cik_raw,
                        "company_name": entry.get("title", company_name),
                    }
    except Exception:
        pass

    # Fallback: browse-edgar query
    try:
        params = {
            "company": company_name or ticker,
            "CIK": ticker,
            "type": "10-K",
            "dateb": "",
            "owner": "include",
            "count": "5",
            "search_text": "",
            "action": "getcompany",
            "output": "atom",
        }
        resp = requests.get(SEC_EDGAR_BROWSE_URL, params=params, headers={
            "User-Agent": SEC_EDGAR_USER_AGENT,
        }, timeout=15)
        if resp.status_code == 200:
            # Parse CIK from the response URL or content
            match = re.search(r"CIK=(\d+)", resp.url)
            if not match:
                match = re.search(r"CIK=(\d+)", resp.text)
            if match:
                cik_raw = match.group(1).zfill(10)
                return {"ticker": ticker, "cik": cik_raw, "company_name": company_name or ticker}
    except Exception as exc:
        return {"ticker": ticker, "error": f"CIK lookup failed: {str(exc)}"}

    return {"ticker": ticker, "error": f"Could not resolve CIK for {ticker}"}


# ── Local Cache Check ─────────────────────────────────────────────────────────

def check_local_cache(ticker: str, filing_type: str) -> dict:
    """Check whether filings for a ticker/type are already cached locally.

    Args:
        ticker: Stock ticker symbol.
        filing_type: Filing type, e.g. '10-K', '10-Q'.

    Returns:
        Dict with 'ticker', 'filing_type', 'cached_files' list, 'cache_fresh' bool.
    """
    ticker = ticker.upper().strip()
    filing_type_safe = filing_type.replace("-", "").replace("/", "_")
    cache_dir = os.path.join(FINANCIAL_FILES_DIR, ticker, filing_type_safe)

    if not os.path.isdir(cache_dir):
        return {
            "ticker": ticker,
            "filing_type": filing_type,
            "cached_files": [],
            "cache_fresh": False,
            "message": "No cache directory found.",
        }

    files = []
    cutoff = datetime.now() - timedelta(days=730)  # 24 months
    newest_mtime = None

    for fname in os.listdir(cache_dir):
        fpath = os.path.join(cache_dir, fname)
        if os.path.isfile(fpath):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            files.append({"filename": fname, "path": fpath, "modified": mtime.strftime("%Y-%m-%d")})
            if newest_mtime is None or mtime > newest_mtime:
                newest_mtime = mtime

    cache_fresh = newest_mtime is not None and newest_mtime >= cutoff

    return {
        "ticker": ticker,
        "filing_type": filing_type,
        "cached_files": files,
        "cache_fresh": cache_fresh,
        "message": f"Found {len(files)} cached file(s). Cache {'is fresh' if cache_fresh else 'is stale or empty'}.",
    }


# ── Search SEC EDGAR ──────────────────────────────────────────────────────────

def search_sec_edgar(ticker: str, cik: str, filing_type: str, months_back: int = 24) -> dict:
    """Search EDGAR submissions for a company and return recent filing metadata.

    Args:
        ticker: Stock ticker symbol.
        cik: Zero-padded 10-digit CIK string.
        filing_type: Filing type to search for (e.g. '10-K').
        months_back: How many months of history to scan.

    Returns:
        Dict with list of matching filings.
    """
    cik_padded = cik.zfill(10)
    url = f"{SEC_EDGAR_SUBMISSIONS_URL}/CIK{cik_padded}.json"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return {"ticker": ticker, "error": f"Failed to fetch EDGAR submissions: {str(exc)}"}

    data = resp.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff_date = datetime.now() - timedelta(days=months_back * 30)
    filings = []

    for i, form in enumerate(forms):
        if form != filing_type:
            continue
        filing_date_str = dates[i] if i < len(dates) else ""
        try:
            filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if filing_date < cutoff_date:
            continue

        accession = accessions[i] if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        cik_clean = cik_padded.lstrip("0") or "0"
        accession_clean = accession.replace("-", "")
        doc_url = (
            f"{SEC_EDGAR_ARCHIVES_URL}/{cik_clean}/{accession_clean}/{doc}"
            if doc else ""
        )

        filings.append({
            "form": form,
            "filing_date": filing_date_str,
            "accession_number": accession,
            "primary_document": doc,
            "document_url": doc_url,
        })

    company_name = data.get("name", ticker)

    return {
        "ticker": ticker,
        "cik": cik_padded,
        "company_name": company_name,
        "filing_type": filing_type,
        "filings_found": len(filings),
        "filings": filings,
    }


# ── Download Filing ───────────────────────────────────────────────────────────

def download_filing(url: str, ticker: str, filing_type: str, filename: str) -> dict:
    """Download a filing document and save it to the local cache.

    Args:
        url: Full URL of the filing document.
        ticker: Stock ticker symbol (used to organise storage).
        filing_type: Filing type (e.g. '10-K').
        filename: Desired filename for the saved file.

    Returns:
        Dict with 'success', 'filepath', and 'bytes_saved' or 'error'.
    """
    ticker = ticker.upper().strip()
    filing_type_safe = filing_type.replace("-", "").replace("/", "_")
    save_dir = os.path.join(FINANCIAL_FILES_DIR, ticker, filing_type_safe)
    os.makedirs(save_dir, exist_ok=True)

    # Sanitise filename
    safe_name = re.sub(r'[^\w\-_\. ]', '_', filename)
    filepath = os.path.join(save_dir, safe_name)

    try:
        time.sleep(0.5)  # Be polite to SEC servers
        headers = {
            "User-Agent": SEC_EDGAR_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/plain",
        }
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()

        with open(filepath, "wb") as fh:
            fh.write(resp.content)

        return {
            "success": True,
            "ticker": ticker,
            "filing_type": filing_type,
            "filepath": filepath,
            "bytes_saved": len(resp.content),
            "url": url,
        }
    except Exception as exc:
        return {"success": False, "error": f"Download failed: {str(exc)}", "url": url}


# ── Tool Definitions ──────────────────────────────────────────────────────────

LOOKUP_CIK_TOOL = {
    "name": "lookup_cik",
    "description": (
        "Look up the SEC EDGAR CIK (Central Index Key) number for a company given its "
        "stock ticker symbol. Returns the 10-digit CIK needed for EDGAR API calls."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g. 'MSFT', 'AAPL').",
            },
            "company_name": {
                "type": "string",
                "description": "Optional company name to help disambiguate.",
            },
        },
        "required": ["ticker"],
    },
}

CHECK_CACHE_TOOL = {
    "name": "check_local_cache",
    "description": (
        "Check whether SEC filings for a given ticker and filing type are already "
        "cached locally. Returns the list of cached files and whether the cache is "
        "fresh (less than 24 months old). Use this BEFORE calling search_sec_edgar."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g. 'MSFT').",
            },
            "filing_type": {
                "type": "string",
                "enum": ["10-K", "10-Q", "8-K", "DEF 14A"],
                "description": "Filing type to check.",
            },
        },
        "required": ["ticker", "filing_type"],
    },
}

SEARCH_EDGAR_TOOL = {
    "name": "search_sec_edgar",
    "description": (
        "Search SEC EDGAR for recent filings of a given type for a company. "
        "Returns filing metadata including dates, accession numbers, and download URLs. "
        "Requires a CIK (use lookup_cik first if you don't have it)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol.",
            },
            "cik": {
                "type": "string",
                "description": "10-digit SEC EDGAR CIK number.",
            },
            "filing_type": {
                "type": "string",
                "enum": ["10-K", "10-Q", "8-K", "DEF 14A"],
                "description": "Type of filing to search for.",
            },
            "months_back": {
                "type": "integer",
                "description": "How many months of history to scan (default 24).",
            },
        },
        "required": ["ticker", "cik", "filing_type"],
    },
}

DOWNLOAD_FILING_TOOL = {
    "name": "download_filing",
    "description": (
        "Download a specific SEC EDGAR filing document and save it to the local "
        "Financial Files cache. Use the document_url returned by search_sec_edgar."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL of the filing document to download.",
            },
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (used for storage organisation).",
            },
            "filing_type": {
                "type": "string",
                "description": "Filing type (e.g. '10-K').",
            },
            "filename": {
                "type": "string",
                "description": "Desired filename for the saved file (include extension).",
            },
        },
        "required": ["url", "ticker", "filing_type", "filename"],
    },
}
