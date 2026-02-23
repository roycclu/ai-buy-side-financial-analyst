"""Configuration for Buy-Side Financial Analyst Agent Team."""

import os
from dotenv import load_dotenv

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env from the project root (silently ignored if the file doesn't exist)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Storage directories
FINANCIAL_FILES_DIR = os.path.join(BASE_DIR, "Financial Files")
FINANCIAL_DATA_DIR = os.path.join(BASE_DIR, "Financial Data")
FINANCIAL_ANALYSES_DIR = os.path.join(BASE_DIR, "Financial Analyses")

# Project registry
PROJECTS_FILE = os.path.join(BASE_DIR, "projects", "projects.json")

# Agent loop limits
MAX_TOKENS = 8192
MAX_AGENT_TURNS = 25

# ── LLM provider ──────────────────────────────────────────────────────────────
# Set LLM_PROVIDER to "anthropic" or "openai".
# "openai" covers OpenAI, Gemini (via their OpenAI-compatible endpoint),
# and any local server that speaks the OpenAI API (e.g. http://127.0.0.1:17777/v1).

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# ── Anthropic settings ────────────────────────────────────────────────────────
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

# ── OpenAI / OpenAI-compatible settings ──────────────────────────────────────
# OPENAI_BASE_URL examples:
#   OpenAI   → https://api.openai.com/v1          (default)
#   Gemini   → https://generativelanguage.googleapis.com/v1beta/openai
#   Local    → http://127.0.0.1:17777/v1
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── SEC EDGAR API settings ────────────────────────────────────────────────────
SEC_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
SEC_EDGAR_ARCHIVES_URL    = "https://www.sec.gov/Archives/edgar/data"
SEC_EDGAR_SEARCH_URL      = "https://efts.sec.gov/LATEST/search-index"
SEC_EDGAR_BROWSE_URL      = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_EDGAR_USER_AGENT      = os.getenv(
    "SEC_EDGAR_USER_AGENT", "BuySideAnalystAgent research@buysideanalyst.com"
)
