# Tech stack and conventions

- Python 3.10+; UI in **Streamlit** (`app.py`).
- **LLM via one doorway** (`llm.ask_json`): provider set by `LLM_PROVIDER` in `.env`:
  `gemini` (google-genai, works today), `bedrock` (boto3 Converse API, once AWS is active) or
  `offline` (no AI; keyword excerpts). Never call an AI SDK anywhere else. Responses are cached in
  `cache/llm`; `MAX_LLM_CALLS_PER_RUN` is the kill switch.
- **Source access only through `sources.py`** (the gateway) → `scraping.py`. No other module may
  use `requests`, search libraries or other network code. `sources_server.py` exposes the
  gateway as an MCP server (mcp v1, FastMCP).
- **Responsible scraping is mandatory** (`docs/responsible_scraping.md`): robots.txt (RFC 9309),
  honest User-Agent with contact, ≥3 s per site, no login/paywall circumvention, cache everything.
  Never spoof a browser User-Agent.
- Open-source extraction: `trafilatura` (HTML), `pypdf` (PDF), `ddgs` (search).
- AI outputs are validated with **Pydantic** (`models.py`) before use.
- Verification is done **in code** (`checks.py`), not by asking the AI to grade itself.
- Secrets only in `.env` (git-ignored). `cache/` and `runs/` are git-ignored.
- Every module starts with a docstring explaining what it does and why (learning project).
- Run `python tests/test_offline.py` before every commit; it needs no internet or AI key.
