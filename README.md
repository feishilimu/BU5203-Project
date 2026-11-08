# RegRadar: an agentic AI researcher for internal audit

RegRadar is a working prototype built for the DBS problem statement *"Agentic AI for Audit: External Driver Researcher"* (BU5203). It helps internal auditors keep track of **external drivers**: new rules, regulatory guidance and official statistics across the markets a bank operates in.

An AI agent finds and recommends official documents, and the auditor chooses which to use. RegRadar then reads each document and produces a structured, cited report covering:

- key dates;
- scope and the bank areas affected;
- a comparison across jurisdictions;
- trends in official statistics.

Every claim is checked against the source by code, and nothing is final until a named human reviewer approves it.

> **Design principle: the AI reads, the code checks, the auditor decides.**

---

## Contents

1. [Problem and framing](#1-problem-and-framing)
2. [What RegRadar does](#2-what-regradar-does)
3. [Key features](#3-key-features)
4. [System design](#4-system-design)
5. [How the AI is used](#5-how-the-ai-is-used)
6. [AI governance](#6-ai-governance)
7. [Risks and mitigations](#7-risks-and-mitigations)
8. [Ethics and responsible use](#8-ethics-and-responsible-use)
9. [Evidence from live testing](#9-evidence-from-live-testing)
10. [Feasibility, value and path to production](#10-feasibility-value-and-path-to-production)
11. [Limitations](#11-limitations)
12. [Setup and running](#12-setup-and-running)
13. [Testing](#13-testing)
14. [Project structure](#14-project-structure)
15. [Configuration](#15-configuration)
16. [Roadmap](#16-roadmap)

---

## 1. Problem and framing

### The problem

Internal audit teams must understand how the external environment affects the bank's risks. For a bank in several markets, that means following many regulators, each publishing in its own format and on its own schedule. Today this research is largely manual:

- finding the right documents on each regulator's website;
- reading them to find issue and effective dates, scope and obligations;
- comparing positions across jurisdictions;
- following official statistics to see which risks are rising or falling.

This work is slow, repetitive and hard to keep consistent, and the reasoning behind a conclusion is rarely recorded in a way another auditor can check.

### How the scope was shaped by the sponsor

The first prototype focused on scam and fraud liability. Sponsor feedback changed the problem framing, and each point became a design decision:

| Sponsor feedback | Design response |
|---|---|
| "Scam liability is too narrow." | A **topic-pack platform**: the same engine runs any external-driver topic; a topic is configuration, not code. |
| "Let the agent find documents from a given domain; the user chooses which to read." | An **agentic discovery step** limited to official domains, with the human choosing what is read. |
| "Dates matter most, shown in tables." | A **key dates timeline and tracker**, with every date checked against its document. |
| "Show scope and relevance, mapped to internal bank areas." | Each document profile lists **who it applies to** and the **internal areas affected**. |
| "No compliance checking." | A deliberate boundary: RegRadar researches and summarises; judging compliance stays with people. |
| "Checking AI text against source text is not useful by itself." | Evidence checks run quietly in the background and surface only as flags and markers, not as the main output. |
| "A chatbot to ask what a policy is about." | An **Ask** tab that answers only from selected documents, with page citations. |
| "Jurisdiction comparison works best for data protection." | A **comparison matrix** of topic questions against jurisdictions, each answer cited. |
| "Trends for statistics." | A **Trends** view built from official statistics, with figures verified and changes calculated by code. |

### Topics in the prototype

| Topic | Default jurisdictions | Report order | Status |
|---|---|---|---|
| Personal data protection and cross-border data transfer | Singapore, Hong Kong, India | Key dates, comparison, trends (only if statistics are found) | Verified live |
| Scams and fraud liability | Singapore, United Kingdom, Australia | Key dates, trends, comparison | Verified live |
| Financial crime (AML/CFT) | Singapore, Hong Kong, India | Key dates, obligations, trends, comparison | Drafted; not yet verified |

Each topic has its own report layout because auditors approach each risk differently: scams lead with trends in losses, data protection with differences between jurisdictions.

---

## 2. What RegRadar does

A run moves through five stages. There are two human gates: one before documents are read, and one before the report is approved.

```
 1. DISCOVER    AI agent searches allowed official domains and recommends
                rule documents and statistics documents
                        |
                HUMAN GATE 1: the auditor ticks what to read
                (plus library files and pasted links)
                        |
 2. READ        documents fetched responsibly, or taken from the library;
                scanned PDFs transcribed by AI
                        |
 3. PROFILE     AI extracts dates, scope, requirements, comparison answers;
                for statistics documents, figures as data points
                        |
 4. CHECK       code verifies dates, quotes and numbers against the source,
                raises flags, calculates trends, detects revised figures
                        |
 5. REVIEW      tracker, timeline, comparison, trends, Ask, report
                        |
                HUMAN GATE 2: reviewer accepts / rejects / follows up each
                document; approval is blocked until high flags are decided
                        |
                Approved report (Markdown) + full audit log (JSON)
```

---

## 3. Key features

### Discovery and sources
- **Agentic discovery.** For each jurisdiction, an AI agent chooses its own searches and page previews within the official domains allowed for that topic, then recommends documents marked as either *rule* or *statistics*, each with a reason and a relevance rating.
- **Access check before reading.** One click tests every recommended link and labels it *readable*, *download by hand* (with a suggested file name) or *already in your library*.
- **Document library.** Documents saved by hand are kept per topic and jurisdiction and reused on every run, so the core set stays stable while the agent's suggestions vary. Files are matched to links by a fingerprint in the file name, and to recommendations by title, so nothing has to be uploaded twice.
- **Manual download helper.** When a site blocks automated access, the app explains why, links to the page, suggests a file name, and lets the reviewer upload the file straight into the current run.
- **AI reading of scanned PDFs.** Documents without a text layer are transcribed page by page by Gemini, with safeguards (see section 6).

### Analysis
- **Document profiles:** issue and effective dates with their supporting text, status (in force, upcoming, consultation), who the document applies to, coverage, exclusions, key requirements, what is new, and the internal areas affected.
- **Key dates:** a timeline and tracker table, with dates found in the document marked as verified and upcoming dates highlighted.
- **Jurisdiction comparison:** each topic's questions answered per jurisdiction, each answer citing its document (for example `[SG-1]`) and marked as verified when its supporting quote is found in the source.
- **Trends from official statistics:** figures extracted from statistics documents, verified against the source, standardised (metric names, currencies, period labels) and charted as line charts and before-and-after charts, with the largest movers highlighted.
- **Revision detection:** when two reports give different values for the same period, the newer figure is charted and both are listed. Differences over 20% are flagged for checking.
- **Ask:** questions answered only from the selected documents, with cited pages. Statistics documents get suitable preset questions.

### Review and audit
- **Review flags** by severity (high, medium, low, info), each with an explanation.
- **Reviewer decisions** (accepted, rejected, follow-up), each with a note, the reviewer's name and a timestamp.
- **Approval gate:** a run cannot be approved while any high-severity document has no decision.
- **Report** in Markdown, with sections in the topic's order and appendices for excluded documents, how sources were found, the source access log and the method.
- **Audit trail:** every agent search and preview, every source attempt and its outcome, every flag, decision and question, saved in one JSON file per run.

---

## 4. System design

### Architecture

```
                         +----------------------------+
                         |   app.py  (Streamlit UI)   |
                         +-------------+--------------+
                                       |
                         +-------------v--------------+
                         | pipeline.py (orchestrator) |  run record = audit trail
                         +--+------+------+------+----+
                            |      |      |      |
          +-----------------+  +---+---+  |  +---+-----------------+
          |                    |       |  |  |                     |
+---------v-------+  +---------v-+ +---v--v--v-+  +----------------v---+
| discovery.py    |  | sources.py| | profiler.py|  | checks.py  stats.py |
| agent + tools   |  | gateway   | | stats.py   |  | dates.py   report.py|
+--------+--------+  +-----+-----+ +-----+------+  +---------------------+
         |                 |             |
+--------v--------+  +-----v------+  +---v-------+
| llm.py          |  | scraping.py|  | ocr.py    |
| Gemini/Bedrock  |  | robots,    |  | scanned   |
| agent loop      |  | rate limit,|  | PDFs      |
+-----------------+  | cache      |  +-----------+
                     +-----+------+
                           |
              sources_server.py  (same gateway published as an MCP server)
```

### Design choices

- **Fixed pipeline, agent inside it.** The agent is free *within* discovery: it chooses which searches to run and what to recommend. The stages around it are fixed, so every run is comparable and auditable.
- **One gateway for all outside content.** Web search, page fetching and uploaded files all pass through `sources.py` and `scraping.py`, so the rules (allowed domains, robots.txt, rate limits, caching, logging) are enforced in one place.
- **MCP server.** `sources_server.py` publishes the same gateway as Model Context Protocol tools (`list_topics`, `list_domains`, `search_domain`, `preview_page`, `read_document`). Other agents and AI tools, such as Kiro, can use the same governed access to sources.
- **Swappable AI provider.** `llm.py` supports Google Gemini, Amazon Bedrock and an offline mode behind one interface. The offline mode uses keyword methods so the app still works without a model.
- **Configuration over code.** Topics, jurisdictions, domains, comparison questions, internal areas, statistics hints and report order live in `topics.py`. Limits and thresholds live in `config.py`.
- **Evidence kept by default.** Fetched pages, AI answers and AI transcriptions are cached by content fingerprint. This makes re-runs free and keeps the exact material each conclusion was based on.

### The agent loop

1. The agent receives the task (topic, jurisdiction, allowed domains) and a menu of two read-only tools: `search_domain` and `preview_page`.
2. On each turn it either calls a tool or returns its recommendations.
3. Code runs only tools on the menu, only within allowed domains, and logs every call.
4. The loop stops at the turn, search and preview limits (the kill switches).
5. A recommended link is accepted only if it appeared in the agent's own search results. Anything else is dropped and logged.
6. If the AI is unavailable, a keyword-based discovery runs instead, and the run records which method was used.

---

## 5. How the AI is used

The AI is used for what it does well (reading, extracting and searching with judgement). Code handles everything that must be exactly right.

| Task | AI does | Code does |
|---|---|---|
| Discovery | Chooses searches, judges relevance, recommends documents | Restricts domains, enforces limits, rejects links the agent didn't find |
| Profiling | Extracts dates, scope, requirements, comparison answers with quotes | Checks every date and quote against the document, raises flags |
| Comparison gaps | A focused second pass for questions left unanswered | Selects the passages that best match each question |
| Statistics | Lists figures with metric, category, period and quote | Verifies each number is in the document, standardises names, units and periods, calculates trends, detects revisions |
| Scanned PDFs | Transcribes page images exactly | Splits into small chunks, checks page counts, caches, flags the document for review |
| Ask | Answers from the selected passages | Checks citations, logs every question |

Other AI design measures:
- **Document text is treated as data, not instructions.** It is wrapped in clearly marked blocks, and text that looks like instructions aimed at the AI is flagged.
- **Answers must be grounded.** Prompts require quotes and page numbers and forbid answers from memory.
- **Structured outputs are validated.** Unusual output shapes (empty values, lists in place of text) are tidied rather than discarded, and broken JSON is retried once.
- **Temporary failures are retried.** Busy-server and rate-limit errors are retried with short waits. Real errors, such as a wrong model name, fail immediately with their message.

---

## 6. AI governance

| Control | How it works |
|---|---|
| Human in the loop | Two gates: the reviewer chooses what is read, and approves or rejects what was found. The AI recommends; people decide. |
| Approval gate | Approval requires a reviewer name and a decision on every document with a high-severity flag. |
| Evidence and verification | Dates, quotes and statistics are checked against the source by code. Unverified answers are marked "quote not found" and listed after verified ones. Unverified figures are never charted. |
| Refusal to guess | A file with almost no readable text is refused rather than profiled, and comparison questions are never asked without supporting passages. |
| Scanned PDF safeguards | Exact transcription only, `[illegible]` instead of guesses, small chunks, missing pages detected by code, empty replies retried page by page with the reason recorded, transcriptions cached as evidence, and the document flagged `read_by_ai_ocr` for a human spot check. |
| Source control | The agent searches only official domains configured per topic and jurisdiction, and cannot recommend links it did not find. |
| Kill switches | Per run: at most 15 documents and 100 AI calls. Per jurisdiction: limits on agent turns (8), searches (8), previews (6) and recommendations (8). |
| Transparency | Every report is marked "DRAFT - NOT FOR RELIANCE" until approved, cites its sources, and includes appendices on how sources were found and how each was accessed. |
| Audit trail | One JSON record per run: inputs, model, every agent tool call, every source attempt and its outcome, profiles, flags, decisions with reviewer and time, questions asked and approval. |
| Reproducibility | Confirmed documents are kept in the library and reused, so runs rest on the same core set. Caching keeps the exact inputs and outputs. |
| Scope boundary | No compliance checking, by design and at the sponsor's request. |

### Review flags

| Flag | Severity | Meaning |
|---|---|---|
| `date_not_in_document` | High | A reported date could not be found in the document |
| `possible_injection` | High | The document contains text that looks like instructions aimed at the AI |
| `not_relevant` | Medium | The AI judged the rule document low relevance to the topic |
| `secondary_source` | Medium | Not an official (Tier 1) source |
| `not_ai_profiled` | Medium | Profiled offline, so fields are rough keyword extracts |
| `read_by_ai_ocr` | Medium | Text transcribed by AI from a scanned PDF |
| `no_effective_date` | Low | The document does not state when it takes effect |
| `effective_soon` | Info | Takes effect within 180 days |

### Mapping to MAS FEAT principles

| Principle | How RegRadar supports it |
|---|---|
| Fairness | Every jurisdiction is researched with the same questions and the same checks, and gaps are shown as "Not stated" rather than filled in. |
| Ethics | Only public documents are processed; websites' access rules are respected; no blocks are bypassed. |
| Accountability | A named reviewer approves each run; every decision is recorded with its reason. |
| Transparency | Every claim is cited; verification status is shown; the method and source log are part of the report. |

---

## 7. Risks and mitigations

| Risk | Mitigation in RegRadar | Residual risk and response |
|---|---|---|
| The AI invents findings | Quotes required and checked; unverified answers marked; files without text refused | A plausible quote could support a wrong reading, so reviewer decisions are required |
| The AI answers from memory | Grounding rules in prompts; no questions without passages; scanned files transcribed and flagged | The flag directs the reviewer to spot-check |
| Wrong dates | Every date checked against the document, with a high flag if missing | Dates written unusually may be flagged wrongly; the reviewer confirms and notes the page |
| Wrong numbers in trends | Numbers verified in the source; trends calculated by code; revisions listed; gaps over 20% flagged | A correct number can be assigned to the wrong category from a garbled table; the 20% flag and reviewer catch these |
| Untrusted or invented sources | Allowed official domains only; links must come from the agent's own results; source tier recorded | The allowed list must be maintained as regulators change websites |
| Prompt injection | Document text treated as data; suspicious instructions flagged as high severity | Pattern-based detection can miss new attacks; the AI has read-only tools, which limits impact |
| Outdated or superseded documents | Status and dates shown; reviewer can reject; revision detection for statistics | A reviewer must still judge currency |
| Over-reliance on AI | Draft marking; approval gate; no compliance conclusions | Training and process ownership in production |
| Inconsistent results between runs | Library of confirmed documents reused; caching; standardised extraction | Agent suggestions vary by design; the core set is stable |
| Runaway cost or loops | Kill switches on documents, AI calls, turns, searches and previews | None material at prototype scale |
| Model or API changes | Provider and model set in configuration; clear errors; offline fallback | Model names change (this happened during the project); a configuration change fixes it |
| Data leakage | Only public documents sent to the AI; no customer or internal data | Production would use a bank-approved environment (see section 10) |

---

## 8. Ethics and responsible use

- **Data privacy.** RegRadar sends only publicly available regulatory documents and statistics to the AI model, never customer, employee or internal bank data. On Gemini's free tier, prompts may be used by Google to improve its products, which is acceptable only because the content is public. A paid tier or a bank-hosted model would be used for anything else.
- **Responsible scraping.** The fetcher:
  - obeys robots.txt;
  - waits at least 3 seconds between requests to the same site;
  - identifies itself honestly in its User-Agent;
  - caches pages so they are not fetched twice;
  - detects bot-check pages;
  - **never works around a block.** When a site blocks automated access, the reviewer downloads the document by hand.

  See `docs/responsible_scraping.md`.
- **Intellectual property.** Documents are used for internal research and cited to their source, and the cache keeps the evidence of what was read. RegRadar does not republish documents.
- **Accountability.** The AI recommends and summarises; a person decides and signs off. Reviewer names and reasons are recorded.
- **Honest limits.** Gaps are shown as "Not stated", failed sources are listed with reasons, and unverified material is marked rather than hidden.

---

## 9. Evidence from live testing

The prototype was tested live on the scams topic (Singapore, United Kingdom, Australia) and the data protection topic (Singapore, Hong Kong, India). Each problem found became a fix and an automated regression test. Examples:

| Found in a live run | What it showed | Fix |
|---|---|---|
| A scanned copy of India's DPDP Act gave no text, and the AI still "answered" questions about it | AI fills gaps from memory if allowed to | Files without text are refused; scanned PDFs are transcribed and flagged |
| An outsourcing guideline "stated" the PDPA's 3-day breach deadline with no supporting quote | Unverified answers must be visible | Answers without a found quote are marked and ranked last |
| S$151.3 million (one scam type) was read as the 2024 total from a garbled table | Extraction errors happen in tables | Gaps over 20% between reports flagged for checking |
| H1 2024 scam losses were S$385.6 million in one police brief and S$522.4 million a year later | Official statistics get revised | Newer figure charted; both values listed |
| "$", "S$" and "SGD", and "Fake Friend Call" and "Fake friend call", split single series | AI naming is inconsistent | Code standardises metrics, categories, currencies and periods |
| A police statistics brief "answered" which scams the liability rules cover | Statistics are not rules | Statistics documents kept out of the rules comparison |
| UK figures written as "year ending March 2025" were not charted | Period formats differ by country | UK year-ending and financial-year periods supported; result matched the ONS headline (+31%) |
| "act as a data intermediary" triggered the injection flag | Security checks need tuning | Narrower pattern |
| The default model name was retired by Google mid-project | External dependencies change | Model set in configuration; clear error messages |

The complete list is in `docs/design_decisions.md`.

---

## 10. Feasibility, value and path to production

### Users and value
- **Users:** internal auditors and audit planners, and second-line risk and compliance teams who track external drivers.
- **When:** audit planning, horizon scanning, and preparing for reviews of areas such as fraud operations, digital banking and data protection.
- **Value:**
  - **Efficiency:** document discovery, reading and first-pass extraction are automated, and the reviewer's time goes to judgement.
  - **Consistency:** the same questions and checks apply to every jurisdiction and every run.
  - **Traceability:** every claim links to its source, and every decision to a reviewer.
  - **Insight:** revised statistics and cross-jurisdiction differences that are easy to miss by hand are surfaced.

### Cost
The prototype runs on Gemini Flash-Lite. On the free tier it costs nothing within Google's rate limits. On a paid tier, a typical run costs in the order of cents. A paid tier also keeps prompts out of model improvement. Reading scanned PDFs adds roughly one AI call per six pages. Re-runs reuse cached results.

### Scalability
A new topic or jurisdiction is a configuration entry in `topics.py`: its domains, questions, internal areas, statistics hints and report order. No code changes are needed.

### Path to production
1. Run the AI on **Amazon Bedrock inside the bank's own AWS environment**. The provider is already supported in `llm.py`.
2. Connect **internal documents** (policies, previous audit findings) through the MCP server, so external drivers can be mapped to internal owners, without compliance checking.
3. Add **single sign-on** and role-based access for reviewers and approvers.
4. Run **scheduled monitoring** that alerts when a new rule or statistics release appears on a watched domain.
5. Keep the same human gates, flags and audit trail.

---

## 11. Limitations

- Some regulator websites block automated access or load content with JavaScript. These documents must be downloaded by hand; the app identifies them and suggests file names.
- AI transcription of scanned PDFs can fail (the model may decline to reproduce long published text) and must be spot-checked when it succeeds.
- Trends need at least two comparable periods. A single statistics release gives only a before-and-after comparison.
- Statistics are compared within a jurisdiction, never across jurisdictions, because sources differ (for example, police-reported cases in Singapore and survey estimates in the UK).
- The date checker recognises common formats; unusual wording may trigger a high flag that the reviewer must clear.
- At most 15 documents per run, by design, so that a reviewer can realistically check every result.
- Discovery depends on a public search engine, whose results and availability vary.
- The financial crime topic is drafted but has not been verified live.

---

## 12. Setup and running

**Requirements:** Python 3.10 or later, and a Google Gemini API key. Alternatively, use Amazon Bedrock credentials, or run without AI in offline mode.

```
python -m venv venv
venv\Scripts\activate            (Windows)
source venv/bin/activate         (macOS / Linux)
pip install -r requirements.txt
```

Create a `.env` file in the project folder (see `.env.example`):

```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
```

**Never commit or share `.env`.** It is listed in `.gitignore`.

Run the tests, then start the app:

```
python tests/test_offline.py
streamlit run app.py
```

The app opens at `http://localhost:8501`. The sidebar shows which AI provider is active.

### Using the app

1. In the sidebar, choose a topic, the jurisdictions and your reviewer name.
2. **Find sources:** run the agent, check which links can be read, download any blocked documents into the library, and tick up to 15 documents.
3. **Read and profile.**
4. Review the topic's tabs (key dates, trends, comparison, Ask), open each flagged profile, and record a decision with a note.
5. **Report and approval:** approve, then download the report and the audit log.
6. **Audit trail:** inspect every search, source, decision and question.

---

## 13. Testing

`tests/test_offline.py` runs without internet or an AI key. It uses stand-in AI responses and a local web server, and covers:

- date parsing and verification, including day-first numeric formats;
- the agent loop with real Gemini SDK types, the Bedrock loop, and agent guardrails;
- profiling, flags, the approval gate and report section order per topic;
- statistics extraction, standardisation, trends, revisions, and UK and half-year periods;
- the comparison second pass and the Ask tab;
- responsible scraping (robots.txt, rate limiting, caching, bot-check detection, User-Agent);
- the manual download helper, library matching and de-duplication;
- scanned PDF transcription, chunking, missing-page detection, retries and flagging;
- a regression test for each issue found in live runs.

Live checks, which need internet and an AI key:

```
python tests/check_ai.py                          AI provider responds
python tests/check_agent.py scams Singapore       watch the agent discover documents
python tests/check_ocr.py library/<file>.pdf      try AI reading of one scanned PDF
```

---

## 14. Project structure

```
app.py               Streamlit interface: tabs per topic, review, approval
pipeline.py          Orchestrates a run; the run record is the audit trail
discovery.py         Discovery agent (tools, guardrails) and keyword fallback
llm.py               AI provider interface (Gemini, Bedrock, offline), agent loop, retries
sources.py           Gateway: domain search, previews, library, manual copies, documents
scraping.py          Responsible fetching: robots.txt, rate limit, cache, bot-check detection
ocr.py               AI transcription of scanned PDFs with safeguards
reading.py           Passage splitting and ranking, untrusted-text handling, injection signals
profiler.py          Document profiles and the focused comparison second pass
models.py            Validated profile schema
checks.py            Flags: dates, injection, relevance, source tier, OCR, effective dates
dates.py             Date parsing and verification against document text
stats.py             Statistics extraction, verification, standardisation, trends, revisions
report.py            Tracker, comparison, trends and the Markdown report
ask.py               Question answering over selected documents with citation checks
topics.py            Topic packs: domains, questions, areas, statistics hints, report order
config.py            Settings, limits and kill switches
sources_server.py    The source gateway published as an MCP server
library/             Documents added by hand (library.json index)
runs/                One JSON audit record per run
cache/               Cached pages, AI answers and transcriptions (evidence)
docs/                Design decisions, experiments, responsible scraping
tests/               Offline test suite and live checks
.kiro/               Kiro steering files and MCP configuration
```

---

## 15. Configuration

Main settings in `config.py`. Most can be overridden in `.env`.

| Setting | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `gemini` if a key is set | `gemini`, `bedrock` or `offline` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model name |
| `MAX_DOCUMENTS_PER_RUN` | 15 | Documents read per run |
| `MAX_LLM_CALLS_PER_RUN` | 100 | AI calls per run (kill switch) |
| `AGENT_MAX_TURNS` / `SEARCHES` / `PREVIEWS` / `RECOMMENDATIONS` | 8 / 8 / 6 / 8 | Agent limits per jurisdiction |
| `MIN_SECONDS_BETWEEN_REQUESTS` | 3.0 | Politeness delay per site |
| `EFFECTIVE_SOON_DAYS` | 180 | Window for the "effective soon" flag |

---

## 16. Roadmap

- **Financial crime (AML/CFT):** verify the drafted topic pack end to end.
- **Change monitoring:** scheduled runs that alert on new rules or statistics releases.
- **Internal documents through MCP:** map external drivers to internal policy owners, without compliance checking.
- **Production deployment:** Bedrock within the bank's AWS, single sign-on, and role-based review and approval.
- **Richer trends:** longer time series from archived releases, and plain-language "main points" generated from verified figures.