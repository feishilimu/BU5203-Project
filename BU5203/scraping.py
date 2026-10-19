"""
scraping.py - downloads public web pages RESPONSIBLY.

WHAT THIS FILE DOES
Given a URL, it downloads the page (HTML or PDF) and returns its main text.
This is the ONLY file in the project that downloads documents from websites.

THE RULES IT ENFORCES (each one is a control you can name in the report)
  1. robots.txt   - before fetching, we read the site's robots.txt (its public
                    "rules for bots") and skip anything it disallows. If robots.txt
                    can't be reached because the server is failing, we assume
                    "not allowed" (the cautious choice, per the robots standard, RFC 9309).
  2. Honest identity - we send a User-Agent naming our bot and a contact email.
                    We never pretend to be a human's browser to dodge blocking.
  3. Rate limit   - at least config.MIN_SECONDS_BETWEEN_REQUESTS between requests
                    to the same site (longer if the site asks via Crawl-delay).
  4. No break-ins - only public http(s) pages. If a site answers 401/403
                    (login or forbidden) or shows a block, we stop - we never try
                    to get around it.
  5. Cache        - every page is saved once in cache/. Repeat runs read the saved
                    copy, so we don't bother the site again, and the evidence
                    behind every finding is preserved for audit.
  6. Size limits  - we refuse oversized downloads.

See docs/responsible_scraping.md for the reasoning behind each rule.
"""
import hashlib
import io
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import trafilatura
from pypdf import PdfReader

import config

_CACHE = config.CACHE_DIR / "pages"
_CACHE.mkdir(exist_ok=True)

# A real regulatory page has thousands of characters. Less than this usually
# means we got a placeholder (JavaScript shell, cookie wall, bot check).
MIN_REAL_TEXT_CHARS = 800
# Phrases typical of bot-protection / blocking pages.
BLOCK_PAGE_SIGNS = ["enable javascript", "javascript is disabled", "access denied", "captcha",
                    "request unsuccessful", "incapsula", "are you a robot", "verify you are human",
                    "checking your browser", "attention required", "request rejected",
                    "support id is", "service is currently unavailable",
                    "using a different device or internet browser"]

_last_request: dict[str, float] = {}        # site -> time of our last request
_robots: dict[str, RobotFileParser | str] = {}  # site -> parsed robots.txt (or "ALLOW_ALL"/"DENY_ALL")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def domain_of(url: str) -> str:
    """'https://www.mas.gov.sg/x' -> 'mas.gov.sg'"""
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_trusted(url: str) -> bool:
    """True if the URL is on (or a sub-site of) a Tier 1 official domain."""
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in config.all_trusted_domains())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cache_file(url: str):
    return _CACHE / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")


# ---------------------------------------------------------------------------
# Rule 1: robots.txt
# ---------------------------------------------------------------------------
def robots_check(url: str) -> tuple[bool, str]:
    """Check the site's robots.txt for our User-Agent. Returns (allowed, reason).

    We download robots.txt ourselves (with our honest User-Agent and a timeout)
    and then hand the text to Python's built-in parser.
    RFC 9309 behaviour:
      - 2xx: obey the rules in the file
      - 4xx: no robots.txt -> everything allowed
      - 5xx or no answer: treat as "disallow everything" (cautious)
    """
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root not in _robots:
        try:
            r = requests.get(root + "/robots.txt", headers={"User-Agent": config.USER_AGENT},
                             timeout=config.REQUEST_TIMEOUT_SECONDS)
            if r.status_code >= 500:
                _robots[root] = ("DENY_ALL", f"robots.txt returned HTTP {r.status_code}; skipped to be safe")
            elif r.status_code >= 400:
                _robots[root] = ("ALLOW_ALL", "no robots.txt on this site")
            else:
                parser = RobotFileParser()
                parser.parse(r.text.splitlines())
                _robots[root] = parser
        except requests.RequestException as e:
            _robots[root] = ("DENY_ALL", f"site unreachable ({type(e).__name__}); skipped to be safe")
    rules = _robots[root]
    if isinstance(rules, tuple):
        return rules[0] == "ALLOW_ALL", rules[1]
    if rules.can_fetch(config.USER_AGENT, url):
        return True, "allowed by robots.txt"
    return False, "the site's robots.txt does not allow automated access to this page"


def _crawl_delay(url: str) -> float:
    """Seconds to wait between requests to this site (the larger of ours and theirs)."""
    parsed = urlparse(url)
    rules = _robots.get(f"{parsed.scheme}://{parsed.netloc}")
    theirs = rules.crawl_delay(config.USER_AGENT) if isinstance(rules, RobotFileParser) else None
    return max(config.MIN_SECONDS_BETWEEN_REQUESTS, float(theirs or 0))


# ---------------------------------------------------------------------------
# Rule 3: rate limit
# ---------------------------------------------------------------------------
def _wait_politely(url: str) -> None:
    site = domain_of(url)
    wait = _crawl_delay(url) - (time.time() - _last_request.get(site, 0))
    if wait > 0:
        time.sleep(wait)
    _last_request[site] = time.time()


# ---------------------------------------------------------------------------
# Turning bytes into text
# ---------------------------------------------------------------------------
def pdf_to_pages(data: bytes) -> list[str]:
    """Return the text of each PDF page (we keep page numbers for citations)."""
    reader = PdfReader(io.BytesIO(data))
    return [(p.extract_text() or "") for p in reader.pages[: config.MAX_PDF_PAGES]]


def html_to_text(html: str) -> tuple[str, str | None, str | None]:
    """Return (main_text, title, published_date) from an HTML page.

    trafilatura strips menus, footers and adverts and keeps the article body.
    """
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    title = date = None
    try:
        meta = trafilatura.extract_metadata(html)
        if meta:
            title, date = meta.title, meta.date
    except Exception:
        pass
    return text, title, date


# ---------------------------------------------------------------------------
# The main function
# ---------------------------------------------------------------------------
def fetch(url: str, official_only: bool = False) -> dict:
    """Download one page responsibly and return a result dict.

    The result always has a "status":
      ok | cached | blocked_by_robots | unreachable | not_official | refused |
      bot_check | too_little_text | error
    Every result is also an audit-log entry: the pipeline stores them all.
    """
    result = {"url": url, "domain": domain_of(url), "checked_at": _now(),
              "tier": 1 if is_trusted(url) else 2}

    if urlparse(url).scheme not in ("http", "https"):
        return {**result, "status": "refused", "reason": "Only public http(s) pages are allowed."}
    if official_only and not is_trusted(url):
        return {**result, "status": "not_official", "reason": "Domain is not on the Tier 1 whitelist."}

    # Rule 5: cache first. No network request at all if we've read it before.
    cached = _cache_file(url)
    if cached.exists():
        saved = json.loads(cached.read_text())
        if len(" ".join(saved.get("pages", []))) >= MIN_REAL_TEXT_CHARS:
            return {**saved, "status": "cached", "checked_at": result["checked_at"]}
        cached.unlink()  # an old placeholder page slipped into the cache: discard and re-check

    # Rule 1: robots.txt
    allowed, why = robots_check(url)
    if not allowed:
        status = "blocked_by_robots" if "robots.txt does not allow" in why else "unreachable"
        return {**result, "status": status, "reason": why}

    # Rule 3: rate limit
    _wait_politely(url)

    try:
        # Rule 2: honest User-Agent. stream=True lets us enforce the size limit.
        r = requests.get(url, headers={"User-Agent": config.USER_AGENT},
                         timeout=config.REQUEST_TIMEOUT_SECONDS, stream=True)
    except requests.RequestException as e:
        return {**result, "status": "error", "reason": f"Download failed: {e}"}

    # Rule 4: stop at login walls / blocks - never try to get around them.
    if r.status_code in (401, 403, 429):
        return {**result, "status": "refused",
                "reason": f"Site answered HTTP {r.status_code} (login required, forbidden or rate-limited). Not retried."}
    if r.status_code >= 400:
        return {**result, "status": "error", "reason": f"HTTP {r.status_code}"}

    # If a whitelisted link redirects somewhere unofficial, don't follow it blindly.
    if official_only and not is_trusted(r.url):
        return {**result, "status": "not_official", "reason": f"Redirected to non-official site {r.url}"}

    # Rule 6: size limit
    data = b""
    for chunk in r.iter_content(64_000):
        data += chunk
        if len(data) > config.MAX_DOWNLOAD_BYTES:
            return {**result, "status": "refused", "reason": "File too large."}

    content_type = r.headers.get("Content-Type", "").lower()
    try:
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            pages = pdf_to_pages(data)
            title, published = None, None
        else:
            text, title, published = html_to_text(data.decode(r.encoding or "utf-8", errors="replace"))
            pages = [text]
    except Exception as e:
        return {**result, "status": "error", "reason": f"Could not read the document: {e}"}

    # Rule 4 again: some sites answer "200 OK" but send a bot-check, cookie wall or
    # "please enable JavaScript" page instead of the content. We treat that as a
    # refusal: we never try to get around it, and we DON'T cache it (otherwise every
    # later run would reuse the placeholder). A human downloads the document instead.
    text = " ".join(p.strip() for p in pages)
    preview = re.sub(r"\s+", " ", text)[:120]
    if any(sign in text.lower() for sign in BLOCK_PAGE_SIGNS):
        return {**result, "status": "bot_check",
                "reason": f"The site sent a bot-check/blocking page, not the document: \"{preview}\""}
    if len(text) < MIN_REAL_TEXT_CHARS:
        return {**result, "status": "too_little_text",
                "reason": f"Only {len(text)} characters - likely a JavaScript, cookie or landing page: \"{preview}\""}

    result.update({
        "status": "ok",
        "final_url": r.url,
        "title": title,
        "published": published,
        "content_type": content_type,
        "pages": pages,                 # list of page texts (one item for HTML)
        "sha256": hashlib.sha256(data).hexdigest(),  # fingerprint of exactly what we read
        "retrieved_at": _now(),
    })
    cached.write_text(json.dumps(result))
    return result