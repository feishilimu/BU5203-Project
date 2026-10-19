# AI in Finance: Agentic AI for Audit (Liability Radar)

**An agentic research assistant for bank internal auditors.**
Topic Chosen: *Scam and Fraud liability. It aims to answer the question: "Who pays when a customer is scammed?"*,
compared across **Singapore, the UK and Australia**. Sponsor brief: DBS Internal Audit,
"Agentic AI for Audit – External Driver Researcher".

## What the Liability Radar does:

| Ask | How Liability Radar does it |
|---|---|
| **Scrape websites** | Reads official regulator documents (whole PDFs and web pages) through one controlled gateway that obeys robots.txt, rate-limits itself, identifies itself honestly and caches what it read. |
| **Read data / findings** | Splits each document into passages, keeps the most relevant ones, and an AI agent turns them into structured findings. Each finding quotes and cites its passage and page. |
| **Display findings readably** | A 4-step screen: choose sources → review findings → approve report → audit trail. The report includes a cross-country comparison table. |
| **Flag what it's unsure of (human in the loop)** | Code checks every finding: is the quote really in the source? Are the numbers in the source? Is the source official? Flags have severities, and the report **can't be approved** until a human has decided on every high-severity finding. Flag criteria live in one place (`checks.py → FLAG_RULES`). |
| **"Where do we find the policies?"** | Three routes: a curated **registry** of official documents, a **library** where a human adds documents the scraper can't reach (in real use, the bank's own internal policy), and **discovery** search limited to official sites, where results only count once a human ticks them. |

---

## Quick start (about 20 minutes)

```bash
# 1. In this folder, create a virtual environment and install
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Settings
cp .env.example .env                # Windows: copy .env.example .env
#    Open .env and add a GEMINI_API_KEY (free: https://aistudio.google.com/apikey)
#    and your CONTACT_EMAIL. No key? It runs in offline mode.

# 3. Prove the controls work (no internet or AI needed)
python tests/test_offline.py

# 4. Start the app (opens http://localhost:8501)
streamlit run app.py
```

**In the app:** type your name in the sidebar → ① Sources: keep the ticks, click **Run analysis**
→ ② Review: open "Evidence", accept or reject flagged findings → ③ Report: approve and download
→ ④ Audit trail: see every source read or blocked.

---

## How it works

```
① Sources (human chooses)      registry  +  library uploads  +  ticked search results
        │                                     sources.py  ← the only door to the outside
        ▼                                     scraping.py ← robots.txt, rate limit, cache
② Read whole documents          reading.py: split into passages → rank → keep the top ones
        ▼
③ Extraction agent              extractor.py: AI writes findings that must quote a passage
        ▼                                     (falls back to excerpts if no AI is available)
④ Code-based checks             checks.py: quote in source? numbers in source? official?
        ▼
⑤ Human review + approval       app.py: accept / reject / follow-up → approve (blocked if HIGH flags open)
        ▼
⑥ Report + audit log            report.py (Markdown), runs/<id>.json (everything that happened)
```

`sources_server.py` publishes the same gateway as an **MCP server** (4 read-only tools), so Kiro
or any MCP client gets exactly the same controlled access. See `.kiro/settings/mcp.json`.

---

## Defining the "unsure" criteria

Open `checks.py`. `FLAG_RULES` lists every rule as `(enabled, severity, meaning)`.
Severity matters: **high** = must be reviewed before approval; **medium/low** = shown, not blocking.
To add a rule: add a line to `FLAG_RULES`, then add the test in `check()`. The app's
"How it works" tab shows the current rules automatically, so users always see the criteria.
