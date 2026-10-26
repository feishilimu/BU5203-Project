# RegRadar 🛰️ (v2)

**An agentic research assistant for bank internal auditors.** Pick a topic and the countries
you operate in. An AI agent searches the regulators' own websites and recommends documents;
you choose which to read. It then profiles each one (**issue date, effective date, scope,
key requirements, internal areas affected**), lays them out in a key-dates tracker and a
cross-country comparison, and answers questions about any policy. A human reviews and
approves before anything is relied on.

Built for the DBS "Agentic AI for Audit – External Driver Researcher" brief. v2 is a
redesign based on the sponsor's feedback: see `docs/design_decisions.md`.

## What's new in v2

| v1 (Liability Radar) | v2 (RegRadar) |
|---|---|
| One topic (scam liability) | **Topic packs**: data protection, financial crime (AML), scams |
| Hand-picked list of links | **Discovery agent** searches allowed regulator domains and recommends documents; you tick them |
| Paragraph "findings" | **Profiles**: dates, status, scope, requirements, areas affected |
| Quote-matching flags | **Date checks** (a wrong deadline is the costly error) and **relevance** |
| Comparison table | **Comparison matrix** across DBS markets (strongest for data protection) |
| — | **Ask the policy** chatbot with page citations |
| — | **Key dates timeline** and countdowns |
| — | **Statistics trends**: the agent recommends 📈 statistics documents; figures verified by code; ▲/▼ charts |
| One report layout | **A report per topic**: each topic orders its sections differently (see below) |

## Quick start

```bash
python -m venv venv
venv\Scripts\activate                 # Mac: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # Mac: cp .env.example .env  -> add GEMINI_API_KEY + CONTACT_EMAIL

python tests/test_offline.py          # 12 checks, no internet or AI needed
python tests/check_ai.py              # is the AI connected?
python tests/check_agent.py           # watch the discovery agent work live (Singapore, data protection)
streamlit run app.py
```

**Bringing over v1's scam documents:** copy the PDFs from your v1 `library` folder into this
`library` folder. `library/library.json` already lists them under the *scams* topic.

## Each topic has its own report

| Topic | Section order (app tabs and report) |
|---|---|
| Scams | Key dates → **Trends** → Liability comparison |
| Data protection | Key dates → Jurisdiction comparison → Trends (only if statistics were found) |
| Financial crime | Key dates → Key obligations → Trends → Comparison |

The order lives in `topics.py` (`report_sections`), so changing a topic's report is a one-line edit.

## Using the app
1. **Sidebar:** choose a topic and jurisdictions, and enter your name.
2. **① Find sources:** click **🤖 Find documents**. Watch the agent search, then tick what to
   read. Add a domain, upload a file or paste a link if something's missing (e.g. MAS blocks
   bots, so download those documents by hand). Then click **▶ Read and profile**.
   Recommendations are marked 📜 rule or 📈 statistics. For trends, tick statistics
   documents that cover several years (e.g. annual scam statistics).
3. **The topic's tabs** follow the order in the table above:
   - **Key dates:** the timeline and tracker table. Open a profile to see the details and
     record your decision.
   - **Trends:** the biggest movers, a line chart per metric (up to 5 categories), a "What
     changed" chart (previous → latest) and a table. Only figures found in the document are charted.
   - **Key obligations** (financial crime) and **Compare** (questions × jurisdictions).
4. **Ask:** "What is this policy about?" and other questions, with cited pages.
5. **Report & approval:** approve, then download the report and the audit log.
6. **Audit trail:** every agent search and preview, every source, decision and question.

## How it works

```
① discovery.py   AI agent: search allowed domains → preview → recommend   (guardrails in code)
        │         YOU tick what to read (+ uploads, pasted links)
② sources.py     responsible fetching (robots.txt, rate limit, cache)  ← the only door to the web
③ profiler.py    AI → profile: dates, status, scope, requirements, areas, comparison answers
④ checks.py      dates verified in the document; relevance; effective-soon alerts
   stats.py       statistics → figures verified in code → trends (▲/▼, %)
⑤ report.py      per-topic sections: tracker, trends, comparison, report        ask.py: grounded Q&A
        │         YOU review each document → approval gate
⑥ runs/<id>.json the audit trail
```

## 📚 Learning path (read in this order)

1. `topics.py`: a topic pack is the whole "configuration" of a topic. *Try:* add Indonesia
   domains to financial crime, or a new question.
2. `discovery.py`: **the agent**. Read the guardrails at the top, then `_discover_with_agent`:
   the two tool functions are where our code limits the AI.
3. `llm.py → run_tool_agent`: the agent loop (the AI asks for a tool, our code runs it, and
   the loop repeats). It's the same idea as v1's `step1_agent_loop.py`, now for Gemini and Bedrock.
4. `models.py`: the profile, the fields banks asked for.
5. `profiler.py`: the profiling prompt's 8 strict rules.
6. `dates.py` and `checks.py`: why dates are checked in code, and the flag rules your team owns.
7. `report.py`: how the tracker and comparison are built (by code, not AI).
8. `ask.py`: how the chatbot stays grounded.
9. `app.py` and `pipeline.py`: the screen and the audit record.
10. `tests/test_offline.py`: each test proves a control works.

## Demo talking points
- **Agentic:** *"The agent decides what to search and what to recommend, within guardrails:
  allowed domains only, budgets, read-only tools, and it can't recommend a link it didn't
  actually find."*
- **Dates first:** *"Every date is checked against the document; ✓ means verified."*
- **Human in the loop:** *"You choose the sources, and you approve the output."*
- **Comparison:** *"Data protection differs across DBS markets. Here's cross-border transfer
  side by side."*
- **Trends:** *"The AI reads the figures, but code checks every number is really in the
  document and does the maths. A wrong number in a chart is worse than no chart."*
- **Honest limits:** non-English sources are translated by the AI, so check key terms; some
  sites block bots, which means a manual upload; trends need statistics covering at least
  two periods.

## Cost (our $85 budget)
A full run costs about $0.15–0.20 on Gemini Flash-Lite (paid tier), or about $0.50 on Flash.
The paid tier also keeps our prompts out of Google's training data. Set a budget alert.
