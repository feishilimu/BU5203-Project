# Tech
- Python 3.10+, Streamlit (altair timeline), Pydantic.
- AI via llm.py only: ask_json (single answers) and run_tool_agent (agent loop with tool calling)
  for Gemini (google-genai) or Bedrock (boto3 Converse); offline fallback everywhere.
- All web access through sources.py -> scraping.py (robots.txt, honest UA, rate limit, cache,
  bot-check detection). sources_server.py exposes the gateway as an MCP server (mcp<2).
- Topic-specific settings ONLY in topics.py. Flag rules ONLY in checks.py.
- Run `python tests/test_offline.py` before every commit.
