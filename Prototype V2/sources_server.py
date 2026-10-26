"""
sources_server.py - the source gateway as an MCP server (read-only tools).

MCP (Model Context Protocol) = a standard way to offer tools to AI apps. This
server offers the SAME tools our discovery agent uses, with the same guardrails,
so any MCP client (Kiro, Claude Desktop, another agent) can only:
  - see which topics and official domains are allowed
  - search ONE allowed official domain
  - preview / read pages through our responsible fetcher (robots.txt, rate limits)
It cannot send, post, change or delete anything.

Register it in Kiro: .kiro/settings/mcp.json (use your venv's python path).
Run by hand (waits silently for a client):  python sources_server.py
"""
from mcp.server.fastmcp import FastMCP

import config
import sources
import topics

mcp = FastMCP("regradar-sources")


def _allowed(domain: str) -> bool:
    return domain in config.all_trusted_domains()


@mcp.tool()
def list_topics() -> dict:
    """Topic packs available, with their jurisdictions and comparison questions."""
    return {tid: {"name": p["name"], "jurisdictions": list(p["domains"]), "questions": p["questions"]}
            for tid, p in topics.TOPICS.items()}


@mcp.tool()
def list_domains(topic_id: str, jurisdiction: str) -> list[str]:
    """Official domains that may be searched for a topic and jurisdiction."""
    return topics.domains_for(topic_id, jurisdiction)


@mcp.tool()
def search_domain(query: str, domain: str) -> list[dict]:
    """Search ONE allowed official domain (e.g. pdpc.gov.sg). Returns titles, URLs, snippets."""
    domain = sources.clean_domain(domain)
    if not _allowed(domain):
        return [{"error": f"{domain} is not an allowed official domain."}]
    return sources.search_domain(query, domain)


@mcp.tool()
def preview_page(url: str) -> dict:
    """Title, opening text and dates of a page on an allowed domain (respects robots.txt)."""
    if not _allowed(sources.clean_domain(url)) and not any(
            sources.on_domain(url, d) for d in config.all_trusted_domains()):
        return {"error": "Only pages on allowed official domains can be previewed."}
    return sources.preview(url)


@mcp.tool()
def read_document(url: str, max_chars: int = 15000) -> dict:
    """Full text of a page/PDF on an allowed domain, wrapped as untrusted data."""
    if not any(sources.on_domain(url, d) for d in config.all_trusted_domains()):
        return {"error": "Only pages on allowed official domains can be read."}
    doc = sources.get_document({"id": "mcp", "jurisdiction": "?", "title": url, "url": url})
    text = "\n\n".join(f"[page {i}] {p}" for i, p in enumerate(doc.get("pages", []), start=1))
    return {"status": doc.get("status"), "reason": doc.get("reason"), "title": doc.get("title"),
            "text": f"<untrusted_document>\n{text[:max_chars]}\n</untrusted_document>",
            "truncated": len(text) > max_chars}


if __name__ == "__main__":
    mcp.run()
