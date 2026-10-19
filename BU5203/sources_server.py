"""
sources_server.py - our source gateway, published as an MCP server.

WHAT IS THIS?
MCP (Model Context Protocol) is an open standard for giving AI agents tools.
An MCP SERVER offers a fixed menu of tools; an MCP CLIENT (an AI agent, Kiro,
Claude Desktop...) can only use what's on the menu.

This server offers exactly four READ-ONLY tools, all built on sources.py, so
any agent that connects inherits our rules: official-domain whitelist,
robots.txt, rate limits, caching. It cannot send, post, change or delete
anything. That's "MCP defines what sources your agent may use".

TRY IT IN KIRO
.kiro/settings/mcp.json registers this server. Open Kiro's MCP SERVERS panel,
enable "liability-radar-sources", then ask Kiro's chat:
"Use list_trusted_sources for Singapore, then read sg-srf-guidelines and tell me
who bears the loss under the SRF."

RUN BY HAND (it waits silently for a client on stdin/stdout):
    python sources_server.py
"""
from mcp.server.fastmcp import FastMCP

import config
import reading
import source_registry
import sources

mcp = FastMCP("liability-radar-sources")


@mcp.tool()
def list_trusted_sources(jurisdiction: str = "") -> dict:
    """List the official (Tier 1) domains and the curated documents for a jurisdiction
    (Singapore, United Kingdom or Australia). Leave empty for all."""
    js = [jurisdiction] if jurisdiction else config.JURISDICTIONS
    return {
        "trusted_domains": {j: config.TRUSTED_DOMAINS.get(j, []) for j in js},
        "curated_documents": [{k: s[k] for k in ("id", "jurisdiction", "title", "url", "why")}
                              for s in source_registry.sources_for(js)],
    }


@mcp.tool()
def search_official_sources(query: str, jurisdiction: str = "") -> list[dict]:
    """Search ONLY official regulator/government websites for documents about the query.
    Returns candidate documents (title, url, snippet). Results are not verified facts."""
    return sources.discover(query, jurisdiction or None, official_only=True)


@mcp.tool()
def read_document(source_id_or_url: str, max_chars: int = 15000) -> dict:
    """Read a curated document (by id, e.g. 'sg-srf-guidelines') or an official URL.
    Returns its text wrapped as UNTRUSTED data, plus where and when it was read."""
    src = source_registry.find(source_id_or_url)
    if src is None:
        src = {"id": "adhoc", "jurisdiction": "Unknown", "title": source_id_or_url,
               "url": source_id_or_url}
        if not sources.scraping.is_trusted(src["url"]):
            return {"status": "not_official", "reason": "Only Tier 1 official domains can be read through this server."}
    doc = sources.get_document(src)
    text = "\n\n".join(f"[page {i}] {p}" for i, p in enumerate(doc.get("pages", []), start=1))
    return {
        "status": doc.get("status"), "reason": doc.get("reason"),
        "title": doc.get("title"), "url": doc.get("url"), "tier": doc.get("tier"),
        "retrieved_at": doc.get("retrieved_at"),
        "text": f"<untrusted_document>\n{text[:max_chars]}\n</untrusted_document>",
        "truncated": len(text) > max_chars,
    }


@mcp.tool()
def find_relevant_passages(source_id: str, top_k: int = 8) -> list[dict]:
    """Return the passages of a curated document most relevant to scam-loss liability,
    with page numbers and IDs, ready to cite."""
    src = source_registry.find(source_id)
    if src is None:
        return [{"error": f"Unknown source id {source_id}"}]
    doc = sources.get_document(src)
    passages = reading.split_passages(doc.get("pages", []), "S1")
    return [{"id": p["id"], "page": p["page"], "score": p["score"], "text": p["text"]}
            for p in reading.select_passages(passages, top_k)]


if __name__ == "__main__":
    mcp.run()  # talks MCP over stdin/stdout
