# Implementation tasks

Tick a task only when it runs. Commit after each one (`git commit -m "T3: ..."`).

- [x] **T1. Agent loop basics** (`learning/step1_agent_loop.py`) — *R12*
- [x] **T2. Gateway + responsible scraping + MCP server** — *R6, R7, R13, R16*
  - [x] `scraping.py` (robots.txt, rate limit, honest UA, cache, size/403 handling)
  - [x] `sources.py`: registry, library, discovery (whitelist enforced), get_document
  - [x] `sources_server.py`: MCP with 4 read-only tools; `.kiro/settings/mcp.json`
- [x] **T3. Reading + structured extraction** — *R2, R5, R14*
  - [x] Whole-document passages, relevance ranking, untrusted-data wrapping
  - [x] Extraction agent with Pydantic validation; offline fallback
- [x] **T4. Checks + flags** — *R8, R13*
- [x] **T5. Pipeline, coverage, run record, approval gate** — *R9, R10, R11, R12*
- [x] **T6. Streamlit UI (sources, review, report, audit)** — *R1, R10, R14, R16*
- [x] **T7. Offline test suite** — *R6–R8, R10, R13*
- [ ] **T8. First live run with Gemini; save the run JSON as evidence** ← NEXT
- [ ] **T9. Tune**: passages per document, prompt wording, flag rules (team criteria)
- [ ] **T10. Evaluation with Person B's gold set; experiments E1–E4** — *R15*
- [ ] **T11. Port from the earlier prototype**: change tracking between runs, Word export
- [ ] **T12. Bedrock switch-over once AWS is verified; v2 free-roaming researcher via the gateway**
- [ ] **T13. Demo hardening**: a cached run for offline demo; rehearse
