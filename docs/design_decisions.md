# RegRadar v2: what changed and why

v2 responds directly to the sponsor meeting (DBS Internal Audit). Each row links a piece of
feedback to a design change and to the code that implements it.

| Sponsor feedback | Change in v2 | Where |
|---|---|---|
| "Let the AI find sources; user chooses instead of hard-coding." "Just put the MAS link and have it search the MAS domain." | **Discovery agent**: given a topic and the allowed official domains, the AI decides what to search, previews pages and recommends documents with reasons. The user ticks which to read. Users can add a domain ("mas.gov.sg") in the app. | `discovery.py`, `sources.search_domain`, tab ① |
| "Use agent to recommend websites." | Recommendations include relevance, document type, why it matters and dates seen. | `discovery.py` |
| "Date is important, must highlight and present results, maybe in a table. Issue date, effective date, highlight key info." | Every document becomes a **profile** with issue date, effective date, transition notes and status. A **Key dates tracker** table (upcoming first, with countdowns) and a **timeline** chart. Dates are checked against the document in code (✓). | `models.Profile`, `profiler.py`, `dates.py`, `report.tracker_rows`, tab ② |
| "What is the effective date? What is the scope?" "No point asking whether you're compliant." | Profiles describe *applies to / covers / exclusions* and key requirements. There's no compliance judgement anywhere. | `profiler.SYSTEM_PROMPT` |
| "Check whether it is relevant; if yes, what is the scope, map to internal." | Relevance rating and reason per document; **internal areas affected**, mapped to each topic's list of bank areas. | `topics.py` (areas), `profiler.py` |
| "Not useful to check whether AI text and source text match." | Sentence-level quote flags removed. Only **dates** are checked as flags (wrong deadlines are costly). Evidence for comparison answers shows as a quiet ✓. | `checks.py` |
| "Have another chatbot to ask what this policy is about." | **Ask** tab: questions answered only from the chosen document(s), with page citations checked by code; logged in the audit trail. | `ask.py`, tab ④ |
| "Comparison across jurisdictions: bank has several locations." "Data protection varies a lot by location." | **Comparison matrix**: topic questions × jurisdictions, each cell cited [SG-1]. Default topic is data protection across DBS markets. | `report.comparison`, tab ③ |
| "Scam liability too narrow." "Consider financial crime / money laundering. Experiment to see which gives the best outcome." | **Topic packs**: data protection, financial crime (AML/CFT) and scams (v1) all run on the same engine. Experiment E1 compares them. | `topics.py`, `docs/experiments.md` |
| "Generate trends for statistics (up/down by category)." | **Trends**: the agent also recommends *statistics* documents (📈), and the user ticks which to include. AI extracts figures; **code** checks that every number appears in the document (unverified figures are never charted) and computes ▲/▼ and % change. Line chart, "What changed" dumbbell chart and a table. | `stats.py`, `discovery.py`, `report._sec_trends`, Trends tab |
| (Our addition) Different topics need different reports. | **Per-topic report order**: Scams → key dates, trends, liability comparison. Data protection → key dates, jurisdiction comparison, trends only if found. Financial crime → key dates, obligations, trends, comparison. App tabs follow the same order. | `topics.py` (`report_sections`), `report.SECTIONS` |

## Decisions we kept from v1 (and why)

- **A fixed overall pipeline, with an autonomous agent inside the discovery step.** The agent has
  real freedom where it adds value (finding documents), while the rest stays predictable and
  auditable. Humans decide at both gates: what is read, and what is approved.
- **Responsible scraping**: robots.txt, an honest User-Agent, rate limits, no bypassing of bot
  checks, a cache kept as evidence. See `docs/responsible_scraping.md`.
- **A model-agnostic AI layer** (Gemini, Bedrock or offline), so the tool works without AI too.
- **An approval gate**, so documents with high flags must be reviewed before the report is approved.
- **An audit trail**: every agent search and preview, every source read or blocked, every
  decision and question, saved per run.

## Agent guardrails (the governance story for the agentic part)

1. The agent can only search domains in the topic pack or ones a human added.
2. Budgets per jurisdiction: AI turns, searches, previews and recommendations (`config.AGENT_*`).
3. **No invented links**: a recommendation must have appeared in the agent's own results.
   Others are dropped and logged.
4. Read-only tools that go through the responsible fetcher.
5. Every tool call is logged and shown in the app ("Agent's working", Audit tab).
6. If the AI fails, a keyword fallback still produces recommendations, so the app never stops.

## What live testing taught us (26 Oct 2026, scams × Singapore)

Each problem found in a live run became a fix plus a regression test (`test_live_run_lessons`).

| Found in a live run | Fix |
|---|---|
| One odd field from the AI (null, or a list instead of text) threw away the whole profile. | Tidy the shape first; only the content rules stay strict. The error names the bad field. |
| Now and then the model returned broken JSON. | One retry with a reminder, and only good answers are cached. |
| "$", "S$" and "SGD" split one series into three; "Fake Friend Call" and "Fake friend call" became two lines. | Code standardises currencies, metric names, category case and period labels ("1H 2024", "January to June 2024" → "H1 2024"). |
| 6.8% → 24.3% showed as "+257%". | Shares are shown as a change in percentage points. |
| Correct figures were rejected because PDF tables break up quotes. | Verify the number itself, which is the check that matters; keep the quote for the reviewer. |
| A police brief "answered" which scams the liability rules cover. | Statistics documents are kept out of the rules comparison and the date flags. |
| The same period differed between reports (H1 2024 losses: S$385.6m in the 2024 brief, S$522.4m in the 2025 brief). | Chart the newer figure and **list every revision**, so auditors see figures that changed rather than having them silently replaced. |
| Contact channels ("via social media") and averages ("per case") were mixed in with scam types. | Moved into separate metrics, so the categories in a chart stay comparable. |
| Asked for a whole profile at once, the AI skipped "Duties on banks" even though it listed those duties. | A focused second pass for unanswered comparison questions, using the passages that best match each question. |
| A statistics brief rated "not relevant" (to the rules) vanished from the report while its figures were charted. | Relevance only excludes rule documents. |
| Contact channels came labelled many ways ("via social media", "messaging platforms contact method", "phone calls"). | Code recognises channel words and keeps channels as a separate breakdown. |
| One "revision" (S$1.11bn vs S$151.3m) was really a figure misread from a garbled PDF table. | Gaps over 20% are marked ⚠️ "check the PDFs" instead of being presented as revisions. |
| Several official PDFs (e.g. India's DPDP Act gazette copy) are scans with no text layer; earlier, the AI "answered" from memory for them. | Unreadable files are refused. Scans are transcribed by Gemini (`ocr.py`): exact transcription, `[illegible]` instead of guesses, small chunks, missing pages detected by code, cached per file, and the document is flagged `read_by_ai_ocr` for a human spot-check. |
