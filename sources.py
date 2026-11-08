"""
sources.py - the GATEWAY: the only way the app (and the agent) reaches documents.

KEY IDEA (same as v1)
Everything from outside - web search, web pages, uploaded files - comes in
through these functions, so the rules (official domains, robots.txt, rate
limits, cache, logging) are enforced in ONE place. sources_server.py publishes
these same functions as an MCP server.

WHAT'S NEW IN v2 (sponsor feedback: "don't hard-code links - give it the MAS
domain and let the agent find the documents")
  search_domain()  search ONE official domain (e.g. pdpc.gov.sg). The discovery
                   agent calls this; it can't search anywhere it hasn't been allowed.
  preview()        a quick look at a page (title, first lines, dates) so the agent
                   can judge relevance before recommending it.
  library          files a human added, now tagged with a topic.
  manual links     a human can paste a link the agent missed.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import config
import ocr
import reading
import scraping

LIBRARY_INDEX = config.LIBRARY_DIR / "library.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_domain(text: str) -> str:
    """'https://www.mas.gov.sg/news' -> 'mas.gov.sg'. Lets users paste a link OR a domain."""
    text = text.strip().lower()
    if "://" not in text:
        text = "https://" + text
    return scraping.domain_of(text)


def on_domain(url: str, domain: str) -> bool:
    host = scraping.domain_of(url)
    return host == domain or host.endswith("." + domain)


# ===========================================================================
# 1. Search ONE domain (the agent's main tool)
# ===========================================================================
def search_domain(query: str, domain: str, max_results: int = 6) -> list[dict]:
    """Search a single website with DuckDuckGo (open source, no API key).

    We ask the search engine for site:<domain> AND check every result ourselves,
    because search engines don't always obey "site:". Never trust a filter you
    don't control.
    """
    from ddgs import DDGS  # imported here so the app still starts if ddgs is missing

    domain = clean_domain(domain)
    try:
        raw = DDGS().text(f"{query} site:{domain}", max_results=max_results * 2) or []
    except Exception as e:  # "no results" and rate limits both raise
        return [{"error": f"search returned nothing ({type(e).__name__})"}]
    results = []
    for r in raw:
        url = r.get("href") or r.get("url") or ""
        if url and on_domain(url, domain):
            results.append({"title": r.get("title") or url, "url": url,
                            "snippet": (r.get("body") or "")[:300]})
        if len(results) >= max_results:
            break
    return results


# ===========================================================================
# 2. Preview a page (cheap look before recommending)
# ===========================================================================
def preview(url: str, chars: int = 1200) -> dict:
    """Title, status, first lines and any dates on the page.

    Uses the same responsible fetcher as everything else, so robots.txt, rate
    limits and bot-check detection all apply. If a site blocks us, the preview
    says so - the agent can still recommend it, and a human downloads it by hand.
    """
    page = scraping.fetch(url)
    text = " ".join(page.get("pages", []))
    return {
        "url": url,
        "status": page["status"],
        "reason": page.get("reason"),
        "title": page.get("title"),
        "dates_found": reading.find_dates(text),
        "opening_text": reading.tidy_pdf_text(" ".join(text.split()))[:chars],
        "needs_manual_download": page["status"] in ("bot_check", "blocked_by_robots", "refused",
                                                    "too_little_text", "unreachable"),
    }


# ===========================================================================
# 3. Library: documents a human added by hand
# ===========================================================================
def _library() -> list[dict]:
    return json.loads(LIBRARY_INDEX.read_text()) if LIBRARY_INDEX.exists() else []


def library_sources(topic_id: str, jurisdictions: list[str]) -> list[dict]:
    """Library documents for this topic and these jurisdictions (only files that exist)."""
    return [{**e, "origin": "library"} for e in _library()
            if e.get("topic") == topic_id and e["jurisdiction"] in jurisdictions
            and (config.LIBRARY_DIR / e["local_file"]).exists()]


_STOP = {"the", "and", "for", "of", "on", "in", "to", "a", "an", "pdf", "guidance", "guide", "guidelines"}


def _title_words(title: str) -> set[str]:
    import re
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower()) if len(w) > 1 and w not in _STOP}


def same_document(a: dict, b: dict) -> bool:
    """Same link, or same jurisdiction and (nearly) the same title.

    LESSON LEARNED (live run): the agent found "New Guidance on Direct Marketing" at one link
    in one run and at another link the next run, so the saved copy wasn't recognised and the
    app asked for it again."""
    if a.get("url") and a.get("url") == b.get("url"):
        return True
    if a.get("jurisdiction") != b.get("jurisdiction"):
        return False
    wa, wb = _title_words(a.get("title", "")), _title_words(b.get("title", ""))
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.6


def library_match(source: dict, topic_id: str) -> dict | None:
    """The library entry that holds this document, if a human already saved it."""
    return next((e for e in library_sources(topic_id, [source.get("jurisdiction", "")]) if same_document(source, e)), None)


def add_to_library(file_name: str, data: bytes, topic_id: str, jurisdiction: str, title: str,
                   url: str = "", official: bool = False, added_by: str = "", kind: str = "rule") -> dict:
    """Save an uploaded file and record who added it, when, and for which topic.

    This is how a human fills gaps the scraper can't: a site that blocks bots
    (MAS), a document behind a download button, or - in real use - the bank's own
    internal policy, which is never on the public web.
    """
    safe_name = Path(file_name).name   # strip any folder path someone sneaks in
    (config.LIBRARY_DIR / safe_name).write_bytes(data)
    entry = {
        "id": "lib-" + hashlib.sha256(data).hexdigest()[:8],
        "topic": topic_id, "jurisdiction": jurisdiction, "title": title or safe_name,
        "url": url, "local_file": safe_name, "official": official,
        "kind": kind,   # "rule" or "statistics" (statistics feed the trend charts)
        "why": "Added by hand to the library.", "added_by": added_by, "added_at": _now(),
    }
    # Same id (same bytes) or same file name (a better copy re-uploaded): the new entry replaces it.
    entries = [e for e in _library() if e["id"] != entry["id"] and e["local_file"] != safe_name] + [entry]
    LIBRARY_INDEX.write_text(json.dumps(entries, indent=2))
    return entry


def manual_link(url: str, jurisdiction: str, title: str = "") -> dict:
    """A link a human pasted in (e.g. one the agent missed)."""
    return {"id": "url-" + hashlib.sha256(url.encode()).hexdigest()[:8], "jurisdiction": jurisdiction,
            "title": title or url, "url": url, "why": "Added by the reviewer.", "origin": "manual",
            "relevance": "reviewer"}


# ===========================================================================
# 3b. Manual downloads: a predictable file name for every link
# ===========================================================================
# Sites like MAS block bots, so a human downloads the file. To make that painless the app
# suggests a file name, e.g.  SG_guide-to-cross-border-data-transfers_3f9a1c.pdf
#   SG      - jurisdiction code (files sort by country)
#   ...     - readable title
#   3f9a1c  - a fingerprint of the LINK. Titles can change between runs; the link doesn't.
# Any file in library/ ending in _<fingerprint> is matched to that link automatically.
FAILED_STATUSES = {"bot_check", "blocked_by_robots", "refused", "too_little_text", "unreachable", "error"}
JUR_CODE = {"Singapore": "SG", "Hong Kong": "HK", "India": "IN", "Indonesia": "ID", "China": "CN",
            "Malaysia": "MY", "Australia": "AU", "United Kingdom": "UK", "Taiwan": "TW", "Thailand": "TH"}


def link_fingerprint(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()[:6]


def suggested_filename(source: dict) -> str:
    """'SG_guide-to-cross-border-data-transfers_3f9a1c.pdf' for a source that needs a manual download."""
    import re
    code = JUR_CODE.get(source.get("jurisdiction", ""), source.get("jurisdiction", "XX")[:2].upper())
    slug = re.sub(r"[^a-z0-9]+", "-", (source.get("title") or "document").lower()).strip("-")[:45].rstrip("-")
    url = source.get("url", "")
    ext = ".html" if re.search(r"\.html?($|\?)", url.lower()) else ".pdf"
    return f"{code}_{slug}_{link_fingerprint(url)}{ext}"


def find_manual_copy(url: str) -> Path | None:
    """A file a human saved in library/ for this link (matched by the link's fingerprint)."""
    if not url:
        return None
    matches = sorted(config.LIBRARY_DIR.glob(f"*_{link_fingerprint(url)}.*"))
    return matches[0] if matches else None


def check_access(source: dict) -> dict:
    """Can the app read this link by itself, or does a human need to download it?

    Uses the same responsible fetcher (robots.txt, rate limit, bot-check detection). A
    readable page is cached, so the later "Read and profile" step doesn't download it again."""
    url = source.get("url", "")
    if copy := find_manual_copy(url):
        return {"state": "have_copy", "label": "📂 your copy in library", "file": copy.name, "reason": ""}
    page = scraping.fetch(url)
    if page["status"] in ("ok", "cached"):
        return {"state": "ok", "label": "✅ readable", "file": "", "reason": ""}
    return {"state": "manual", "label": "⬇️ download by hand", "file": suggested_filename(source),
            "reason": f"{page['status']}: {page.get('reason') or ''}"}


# ===========================================================================
# 4. Getting a document's full text
# ===========================================================================
def _read_local(path: Path) -> tuple[list[str], str | None]:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if b"%PDF" in data[:1024]:      # trust the content, not the name (same rule as downloads)
        return scraping.pdf_to_pages(data), None
    if data.lstrip()[:1] == b"<" or (suffix in (".html", ".htm") and b"<" in data[:2000]):   # looks like HTML
        text, title, _ = scraping.html_to_text(data.decode("utf-8", errors="replace"))
        return [text], title
    return [data.decode("utf-8", errors="replace")], None


def get_document(source: dict) -> dict:
    """Return the source plus status, pages (list of page texts), tier and fingerprint."""
    url = source.get("url", "")
    tier = 1 if (url and scraping.is_trusted(url)) or source.get("official") else 2
    base = {**source, "tier": tier}
    local = config.LIBRARY_DIR / source["local_file"] if source.get("local_file") else None
    if (local is None or not local.exists()) and (copy := find_manual_copy(url)):
        # A human already downloaded this link by hand: use their copy, not the web.
        local, base = copy, {**base, "local_file": copy.name, "manual_copy": True}
    if local is not None and local.exists():
        pages, title = _read_local(local)
        text = " ".join(pages).lower()
        if len(text.strip()) < scraping.MIN_REAL_TEXT_CHARS and local.read_bytes()[:1024].find(b"%PDF") >= 0:
            try:   # a scan: let Gemini transcribe the page images (see ocr.py for the safeguards)
                o = ocr.read_scanned_pdf(local.read_bytes(), progress=source.get("_progress") or (lambda m: None))
                got = len(" ".join(o["pages"]).strip())
                if got < scraping.MIN_REAL_TEXT_CHARS:
                    why = "; ".join(o.get("problems", [])[:3])
                    hint = (" - Gemini declined to reproduce this published text word for word (RECITATION)"
                            if "RECITATION" in why else "")
                    base = {**base, "ocr_error": f"the AI returned only {got} characters from {o['pages_total']} "
                                                 f"page(s){hint}{f'. Details: {why}' if why else ''}"}
                else:
                    return {**base, "status": "library", "pages": o["pages"], "ocr": {k: v for k, v in o.items() if k != "pages"},
                            "title": source.get("title") or local.stem,
                            "retrieved_at": datetime.fromtimestamp(local.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                            "sha256": hashlib.sha256(local.read_bytes()).hexdigest()}
            except Exception as e:   # no Gemini, call limit, API error -> report it as unreadable
                base = {**base, "ocr_error": f"{type(e).__name__}: {e}"[:160]}
            return {**base, "status": "too_little_text", "pages": [],
                    "reason": f"'{local.name}' is a SCANNED PDF (pictures of pages, no text layer). "
                              + (f"AI reading failed ({base['ocr_error']}). " if base.get("ocr_error") else "")
                              + "Find a text version, or check Gemini is set up so the AI can read the page images."}
        if len(text.strip()) < scraping.MIN_REAL_TEXT_CHARS:
            # A scanned PDF or a saved landing page: profiling it would only invite the AI to
            # fill gaps from memory (live run: identical made-up answers for different files).
            return {**base, "status": "too_little_text", "pages": [],
                    "reason": f"The file '{local.name}' has only {len(text.strip())} characters of readable text "
                              "(scanned images or a saved web page?). Download the document's PDF version instead."}
        if any(sign in text for sign in scraping.BLOCK_PAGE_SIGNS) and len(text) < 3000:
            return {**base, "status": "error", "pages": [],
                    "reason": f"The saved file '{local.name}' is the site's blocking page, not the document. "
                              "Download it again from the link (use the PDF button / 'Save as PDF')."}
        return {**base, "status": "library", "pages": pages, "title": source.get("title") or title,
                "retrieved_at": datetime.fromtimestamp(local.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(local.read_bytes()).hexdigest()}
    if not url:
        return {**base, "status": "error", "reason": "No file and no link.", "pages": []}
    fetched = scraping.fetch(url)
    return {**base, **{k: v for k, v in fetched.items() if k not in ("url", "tier", "title")},
            "pages": fetched.get("pages", []),
            "title": source.get("title") or fetched.get("title") or url}
