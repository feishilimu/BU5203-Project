"""
config.py - every setting in one place.

WHAT THIS FILE DOES
Holds the settings that the rest of the code reads: which AI model to use,
which countries we cover, which websites count as "official", how politely we
scrape, and the safety limits for one run.

Several governance controls live here as plain, inspectable settings:
  - TRUSTED_DOMAINS     -> "Scope": which sources count as official (Tier 1)
  - SCRAPING settings   -> responsible web access (see docs/responsible_scraping.md)
  - RUN LIMITS          -> "Kill switch": hard caps so a run can't spiral
A risk reviewer can read this one file and see the boundaries of the tool.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env and puts its values into os.environ

PROJECT_DIR = Path(__file__).parent
CACHE_DIR = PROJECT_DIR / "cache"      # saved copies of every page we read (evidence)
RUNS_DIR = PROJECT_DIR / "runs"        # one JSON audit log per run
LIBRARY_DIR = PROJECT_DIR / "library"  # documents a human added by hand (e.g. a PDF)
for folder in (CACHE_DIR, RUNS_DIR, LIBRARY_DIR):
    folder.mkdir(exist_ok=True)

TOPIC = "Scam and fraud liability: who pays when a customer is scammed?"

# ===========================================================================
# 1. WHICH AI MODEL ("LLM PROVIDER")
# ===========================================================================
# The app works with three "brains", chosen in .env:
#   gemini   - Google Gemini (free API key; works today while AWS is pending)
#   bedrock  - Amazon Bedrock (Nova / Claude) once your AWS account is active
#   offline  - NO AI at all: the app still scrapes, reads, ranks passages and
#              shows excerpts. Useful for testing, and a fair "no-AI baseline"
#              to compare against in your evaluation.
# If LLM_PROVIDER is not set, we pick the first one that has a key.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or ""
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"

AWS_REGION = os.getenv("AWS_REGION") or "us-east-1"
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL") or ""  # copy from Bedrock > Model catalog


def _default_provider() -> str:
    if GEMINI_API_KEY:
        return "gemini"
    if os.getenv("AWS_BEARER_TOKEN_BEDROCK") and BEDROCK_MODEL:
        return "bedrock"
    return "offline"


# Note: `or` (not a default argument) so that a BLANK line like "LLM_PROVIDER=" in
# .env also means "choose automatically". os.getenv returns "" for blank values.
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or _default_provider()).strip().lower()

# ===========================================================================
# 2. JURISDICTIONS AND TRUSTED (TIER 1) DOMAINS
# ===========================================================================
# Tier 1 = the regulator, government or official legislation site itself.
# Everything else (news, law firms, blogs) is Tier 2: useful context for the
# "industry developments" section, but flagged as secondary.
JURISDICTIONS = ["Singapore", "United Kingdom", "Australia"]

TRUSTED_DOMAINS = {
    "Singapore": [
        "mas.gov.sg",        # Monetary Authority of Singapore (bank regulator)
        "imda.gov.sg",       # telco regulator (telco duties under the SRF)
        "police.gov.sg",     # Singapore Police Force (scam statistics)
        "mha.gov.sg",        # Ministry of Home Affairs (anti-scam laws)
        "sso.agc.gov.sg",    # Singapore Statutes Online (the law itself)
    ],
    "United Kingdom": [
        "psr.org.uk",        # Payment Systems Regulator (APP scam reimbursement)
        "fca.org.uk",        # Financial Conduct Authority
        "gov.uk",
        "legislation.gov.uk",
    ],
    "Australia": [
        "treasury.gov.au",   # policy owner of the Scams Prevention Framework
        "accc.gov.au",       # competition & consumer regulator
        "asic.gov.au",       # financial services regulator
        "legislation.gov.au",
        "scamwatch.gov.au",
    ],
}


def all_trusted_domains(jurisdictions: list[str] | None = None) -> list[str]:
    """Flatten TRUSTED_DOMAINS into one list (optionally for some countries only)."""
    keys = jurisdictions or list(TRUSTED_DOMAINS)
    return [d for j in keys for d in TRUSTED_DOMAINS.get(j, [])]


# ===========================================================================
# 3. RESPONSIBLE SCRAPING SETTINGS (see docs/responsible_scraping.md)
# ===========================================================================
# We tell websites honestly who we are. Put a real contact email in .env so a
# site owner could reach you - this is standard good practice for bots.
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL") or "contact-not-set"
USER_AGENT = f"LiabilityRadar/0.2 (university research prototype; contact: {CONTACT_EMAIL})"

MIN_SECONDS_BETWEEN_REQUESTS = 3.0   # per website; we use the site's Crawl-delay if longer
REQUEST_TIMEOUT_SECONDS = 20
MAX_DOWNLOAD_BYTES = 15_000_000      # refuse anything bigger than ~15 MB
MAX_PDF_PAGES = 80                   # read whole documents, not just the first few pages

# ===========================================================================
# 4. READING SETTINGS
# ===========================================================================
# Documents are cut into "passages" (a few sentences each). We only send the
# most relevant passages to the AI - cheaper, faster, and every finding can
# point to the exact passage it came from.
PASSAGE_TARGET_CHARS = 1100
TOP_PASSAGES_PER_DOCUMENT = 8

# Words that signal a passage is about our topic. Weight = how strong a signal.
TOPIC_KEYWORDS = {
    3: ["bear the loss", "bear any loss", "bear losses", "reimburse", "compensat",
        "liable", "liability", "refund", "payout", "pay out", "shared responsibility",
        "authorised push payment", "app fraud", "app scam", "seemingly authorised",
        "self-effected", "unauthorised transaction"],
    2: ["scam", "fraud", "phishing", "duty", "duties", "cooling off", "notification alert",
        "effective date", "commence", "maximum", "cap ", "claim", "investigation",
        "consultation", "excess", "gross negligence", "vulnerable"],
    1: ["bank", "financial institution", "telco", "consumer", "customer",
        "account holder", "victim", "payment service provider"],
}

# ===========================================================================
# 5. RUN LIMITS ("kill switch" settings)
# ===========================================================================
MAX_DOCUMENTS_PER_RUN = 20
MAX_LLM_CALLS_PER_RUN = 12
MAX_PROMPT_CHARS = 60_000   # if a country's passages exceed this, we split into batches