# Project structure

```
liability-radar/
├── app.py               # Streamlit UI: ① sources ② review ③ report & approval ④ audit
├── pipeline.py          # orchestrator: fixed steps, run record (audit trail), approval gate
├── sources.py           # GATEWAY: registry, library, discovery, get_document (only door out)
├── scraping.py          # responsible fetching: robots.txt, rate limit, honest UA, cache
├── source_registry.py   # curated official documents per jurisdiction
├── reading.py           # split whole documents into passages, rank, injection detection
├── extractor.py         # extraction agent (AI) + offline fallback
├── checks.py            # FLAG_RULES: code-based verification → flags
├── report.py            # Markdown report from reviewed findings
├── models.py            # Pydantic data shapes
├── llm.py               # one doorway to Gemini / Bedrock / offline
├── config.py            # all settings and control limits
├── sources_server.py    # the gateway as an MCP server (4 read-only tools)
├── learning/            # step1_agent_loop.py: free-roaming agent using the same gateway
├── tests/               # test_offline.py: proves the controls without internet/AI
├── library/             # documents added by hand (+ library.json index)
├── docs/                # responsible_scraping.md, experiments.md
├── .kiro/               # steering, specs, settings/mcp.json
├── cache/               # (git-ignored) saved pages + AI answers = evidence
└── runs/                # (git-ignored) one JSON audit log per run
```

Rule: a new file must fit this structure; update this document first.
