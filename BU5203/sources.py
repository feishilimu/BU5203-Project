"""
sources.py - the GATEWAY: the only way the rest of the app gets documents.

KEY IDEA
Everything outside our app (websites, search engines, uploaded files) comes in
through the functions in this file. Nothing else in the pipeline touches the
network. That gives us ONE place to enforce the rules and ONE place to log
every access - exactly the "source discipline" idea behind MCP.

In fact, sources_server.py publishes these same functions as an MCP server,
so any MCP client (Kiro, Claude Desktop, or our own agents later) gets the
same controlled access and nothing more.

THE THREE KINDS OF SOURCE
  registry  - curated official documents (source_registry.py)
  library   - files a human added by hand (library/ folder)
  discovery - web search results limited to official sites; they only become
              sources after a human ticks them in the app
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import config
import scraping
import source_registry

LIBRARY_INDEX = config.LIBRARY_DIR / "library.json"


# ===========================================================================
# 1. Listing sources
# ===========================================================================
def registry_sources(jurisdictions: list[str]) -> list[dict]:
    return [{**s, "origin": "registry"} for s in source_registry.sources_for(jurisdictions)]


def library_sources(jurisdictions: list[str]) -> list[dict]:
    """Documents a human uploaded (stored in library/library.json)."""
    if not LIBRARY_INDEX.exists():
        return []
    entries = json.loads(LIBRARY_INDEX.read_text())
    return [{**e, "origin": "library"} for e in entries if e["jurisdiction"] in jurisdictions]


def add_to_library(file_name: str, data: bytes, jurisdiction: str, title: str,
                   url: str = "", official: bool = False, section: str = "A",
                   added_by: str = "") -> dict:
    """Save an uploaded file into library/ and record who added it and when.

    This is how a human closes gaps the scraper can't: a PDF behind a
    JavaScript download button, a document a mentor emailed you, or (in real
    use) the bank's own internal policy, which is never on the public web.
    """
    safe_name = Path(file_name).name  # strip any folder path someone sneaks in
    (config.LIBRARY_DIR / safe_name).write_bytes(data)
    entry = {
        "id": "lib-" + hashlib.sha256(data).hexdigest()[:8],
        "jurisdiction": jurisdiction,
        "title": title or safe_name,
        "url": url,
        "local_file": safe_name,
        "publisher": "Added by reviewer",
        "kind": "uploaded",
        "section": section,
        "official": official,   # the human vouches it is an official document
        "why": "Added manually to the library.",
        "added_by": added_by,
        "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    entries = json.loads(LIBRARY_INDEX.read_text()) if LIBRARY_INDEX.exists() else []
    entries = [e for e in entries if e["id"] != entry["id"]] + [entry]
    LIBRARY_INDEX.write_text(json.dumps(entries, indent=2))
    return entry


# ===========================================================================
# 2. Discovery: search limited to official sites
# ===========================================================================
def suggested_queries(jurisdiction: str) -> list[str]:
    """Ready-made searches for spotting new official documents."""
    return [
        f"{jurisdiction} scam victim reimbursement bank liability",
        f"{jurisdiction} authorised push payment scam compensation rules",
    ]


def discover(query: str, jurisdiction: str | None = None,
             official_only: bool = True, max_results: int = 6) -> list[dict]:
    """Search the web (DuckDuckGo, open source, no API key) for candidate sources.

    With official_only=True we (a) ask the search engine for official domains
    only, and (b) double-check every result ourselves, because search engines
    don't always obey "site:" filters. Never trust a filter you don't control.
    """
    from ddgs import DDGS  # imported here so the app still starts if ddgs is missing

    q = query
    if official_only:
        domains = config.all_trusted_domains([jurisdiction] if jurisdiction else None)
        q += " (" + " OR ".join(f"site:{d}" for d in domains) + ")"
    try:
        raw = DDGS().text(q, max_results=max_results * 2) or []
    except Exception as e:  # "no results" and rate limits both raise
        print(f"   (search returned nothing: {e})")
        return []

    found = []
    for r in raw:
        url = r.get("href") or r.get("url") or ""
        if not url or (official_only and not scraping.is_trusted(url)):
            continue
        found.append({
            "id": "web-" + hashlib.sha256(url.encode()).hexdigest()[:8],
            "jurisdiction": jurisdiction or "Unknown",
            "title": r.get("title") or url,
            "url": url,
            "publisher": scraping.domain_of(url),
            "kind": "unknown",
            "section": "A" if scraping.is_trusted(url) else "B",
            "why": (r.get("body") or "")[:300],
            "origin": "discovery",
        })
        if len(found) >= max_results:
            break
    return found


# ===========================================================================
# 3. Getting a document's text
# ===========================================================================
def _read_local(path: Path) -> tuple[list[str], str | None, str | None]:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return scraping.pdf_to_pages(data), None, None
    if suffix in (".html", ".htm"):
        text, title, date = scraping.html_to_text(data.decode("utf-8", errors="replace"))
        return [text], title, date
    return [data.decode("utf-8", errors="replace")], None, None


def get_document(source: dict) -> dict:
    """Return a Document dict for a source (from the library or the web).

    Output fields: everything from the source entry, plus
      status, reason, pages (list of page texts), tier, retrieved_at, sha256...
    """
    url = source.get("url", "")
    tier = 1 if (url and scraping.is_trusted(url)) or source.get("official") else 2
    base = {**source, "tier": tier}

    # A manually downloaded copy in library/ wins (e.g. when the website blocks bots).
    # The original url is kept, so the report still links to the official page.
    local = config.LIBRARY_DIR / source["local_file"] if source.get("local_file") else None
    if local is not None and not local.exists() and not url:
        return {**base, "status": "error", "reason": f"Library file not found: {local.name}", "pages": []}
    if local is not None and local.exists():
        path = local
        pages, title, published = _read_local(path)
        return {**base, "status": "library", "pages": pages,
                "published": source.get("published") or published,
                "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    fetched = scraping.fetch(url)
    return {**base, **{k: v for k, v in fetched.items() if k not in ("url", "tier")},
            "pages": fetched.get("pages", []),
            "title": source.get("title") or fetched.get("title") or url}