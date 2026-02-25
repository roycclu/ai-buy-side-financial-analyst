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
# Set LLM_PROVIDER to one of three options:
#   "anthropic" → Anthropic Claude (supports extended thinking)
#   "openai"    → OpenAI or Gemini via their cloud APIs
#   "llama"     → Local Llama-compatible server (Ollama, local-llm-server, vLLM, etc.)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# ── Anthropic settings ────────────────────────────────────────────────────────
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")

# ── OpenAI cloud settings (OpenAI or Gemini only — not for local servers) ────
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Llama / local server settings ─────────────────────────────────────────────
# One-liner to switch port:  LLAMA_PORT=17777  (local-llm-server)
#                        or  LLAMA_PORT=11434  (Ollama)
# The base URL is auto-derived from host+port unless LLAMA_BASE_URL is set directly.
LLAMA_HOST     = os.getenv("LLAMA_HOST", "127.0.0.1")
LLAMA_PORT     = int(os.getenv("LLAMA_PORT", "17777"))
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", f"http://{os.getenv('LLAMA_HOST', '127.0.0.1')}:{os.getenv('LLAMA_PORT', '17777')}/v1")
LLAMA_MODEL    = os.getenv("LLAMA_MODEL", "llama3.2:1b")

# ── SEC EDGAR API settings ────────────────────────────────────────────────────
SEC_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
SEC_EDGAR_ARCHIVES_URL    = "https://www.sec.gov/Archives/edgar/data"
SEC_EDGAR_SEARCH_URL      = "https://efts.sec.gov/LATEST/search-index"
SEC_EDGAR_BROWSE_URL      = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_EDGAR_USER_AGENT      = os.getenv(
    "SEC_EDGAR_USER_AGENT", "BuySideAnalystAgent research@buysideanalyst.com"
)
