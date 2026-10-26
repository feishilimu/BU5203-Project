"""
config.py - settings shared by every topic.

WHAT CHANGED FROM v1
v1 had one topic baked in (scam liability). In v2 everything topic-specific
(countries, regulator websites, keywords, comparison questions) lives in
topics.py as a "topic pack". This file only holds settings that apply to all
topics: which AI to use, how politely we scrape, and the safety limits.

GOVERNANCE CONTROLS THAT LIVE HERE (cite these in the report)
  - responsible scraping settings  -> docs/responsible_scraping.md
  - RUN LIMITS                     -> the "kill switch": hard caps per run
  - AGENT LIMITS                   -> how far the discovery agent may roam
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).parent
CACHE_DIR = PROJECT_DIR / "cache"      # saved pages + AI answers (evidence, and free re-runs)
RUNS_DIR = PROJECT_DIR / "runs"        # one JSON audit log per run
LIBRARY_DIR = PROJECT_DIR / "library"  # documents a human added by hand
for folder in (CACHE_DIR, RUNS_DIR, LIBRARY_DIR):
    folder.mkdir(exist_ok=True)

# ===========================================================================
# 1. WHICH AI MODEL: gemini | bedrock | offline   (set LLM_PROVIDER in .env)
# ===========================================================================
# `or` (not a default) so that a BLANK line like "LLM_PROVIDER=" in .env also
# means "choose automatically" - os.getenv returns "" for blank values.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"
AWS_REGION = os.getenv("AWS_REGION") or "us-east-1"
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL") or ""


def _default_provider() -> str:
    if GEMINI_API_KEY:
        return "gemini"
    if os.getenv("AWS_BEARER_TOKEN_BEDROCK") and BEDROCK_MODEL:
        return "bedrock"
    return "offline"


LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or _default_provider()).strip().lower()

# ===========================================================================
# 2. RESPONSIBLE SCRAPING (unchanged from v1 - see docs/responsible_scraping.md)
# ===========================================================================
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL") or "contact-not-set"
USER_AGENT = f"RegRadar/0.3 (university research prototype; contact: {CONTACT_EMAIL})"
MIN_SECONDS_BETWEEN_REQUESTS = 3.0
REQUEST_TIMEOUT_SECONDS = 20
MAX_DOWNLOAD_BYTES = 15_000_000
MAX_PDF_PAGES = 80


def all_trusted_domains(jurisdictions: list[str] | None = None) -> list[str]:
    """Every official domain in every topic pack (Tier 1 = official source).

    Imported lazily so topics.py and config.py don't import each other at start-up.
    """
    import topics
    domains = []
    for pack in topics.TOPICS.values():
        for j, ds in pack["domains"].items():
            if jurisdictions is None or j in jurisdictions:
                domains += ds
    return sorted(set(domains))


# ===========================================================================
# 3. READING
# ===========================================================================
PASSAGE_TARGET_CHARS = 1100
TOP_PASSAGES_PER_DOCUMENT = 10   # a bit more than v1: profiles need dates AND scope

# ===========================================================================
# 4. LIMITS ("kill switch")
# ===========================================================================
MAX_DOCUMENTS_PER_RUN = 15
MAX_LLM_CALLS_PER_RUN = 100      # agent turns + profiles + statistics extraction + Q&A
MAX_PROMPT_CHARS = 60_000

# The discovery agent (discovery.py) - how far it may roam per jurisdiction.
AGENT_MAX_TURNS = 8              # AI decisions per jurisdiction before it must stop
AGENT_MAX_SEARCHES = 8           # web searches per jurisdiction
AGENT_MAX_PREVIEWS = 6           # page previews per jurisdiction
AGENT_MAX_RECOMMENDATIONS = 8    # documents it may recommend per jurisdiction (rules + statistics)

# Dates are what banks care about most: highlight anything taking effect soon.
EFFECTIVE_SOON_DAYS = 180