"""
tests/test_offline.py - proves RegRadar's controls work, with NO internet and NO AI key.

Run from the project folder:   python tests/test_offline.py

To test AI steps without an AI, we swap in FAKES that behave like the real thing
(including deliberate mistakes), and fake search results. What's covered:
  dates      - dates are found in any format; invented dates are caught
  agent      - stays on allowed domains, respects budgets, can't recommend links it
               never saw; the Gemini AND Bedrock loops handle real tool-call formats
  profile    - invented dates flagged HIGH; unknown areas/questions dropped
  ask        - answers cite pages; fake citations are marked unverified
  approval   - blocked until HIGH-flag documents are reviewed
  statistics - only figures found in the document are charted; trends computed by code
  reports    - each topic gets its own section order
  scraping   - robots.txt, rate limit, bot-check pages, honest User-Agent
"""
import json
import os
import sys
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["LLM_PROVIDER"] = "offline"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

import ask        # noqa: E402
import checks     # noqa: E402
import config     # noqa: E402
import dates      # noqa: E402
import discovery  # noqa: E402
import llm        # noqa: E402
import profiler   # noqa: E402
import pipeline   # noqa: E402
import reading    # noqa: E402
import report     # noqa: E402
import scraping   # noqa: E402
import sources    # noqa: E402
import stats      # noqa: E402
import topics     # noqa: E402

TMP = Path(tempfile.mkdtemp())
config.RUNS_DIR = TMP
scraping._CACHE = TMP
llm._CACHE = TMP
SRF = sources.library_sources("scams", ["Singapore"])[0]


def test_dates():
    text = "Issue Date: 24 October 2024. These Regulations come into operation on March 1, 2026; Part 3 in September 2027."
    assert dates.stated_in("24 October 2024", text) and dates.stated_in("2024-10-24", text)
    assert dates.stated_in("1 March 2026", text) and dates.stated_in("Sept 2027", text)
    assert not dates.stated_in("2024-10-16", text), "numbers scattered in the text must not count as a date"
    assert not dates.stated_in("1 September 2027", text), "an invented day must not match a month-only date"
    print("✓ dates: any format accepted; invented dates rejected")


def test_reading_boosts_dates():
    plain = "These Regulations come into operation on 1 March 2026."
    assert reading.relevance(plain, topics.get("data_protection")["keywords"]) > 0, \
        "a passage stating when rules take effect must be kept even without topic words"
    print("✓ reading: passages that state effective dates are prioritised")


def _fake_search(query, domain, max_results=6):
    return [{"title": f"{domain} guideline on {query[:20]}", "url": f"https://www.{domain}/doc-{len(query)}",
             "snippet": "personal data transfer guidelines effective 1 March 2026"}]


def _fake_preview(url, chars=1200):
    return {"url": url, "status": "ok", "title": "Guideline", "dates_found": ["1 March 2026"],
            "opening_text": "Guidelines on cross-border transfer of personal data", "needs_manual_download": False}


def test_agent_guardrails():
    """Simulate an AI that tries to break the rules; the code must stop it."""
    sources.search_domain, sources.preview = _fake_search, _fake_preview

    def fake_agent(system, task, tools, functions, max_turns, trace):
        ok = functions["search_domain"](query="cross-border transfer", domain="pdpc.gov.sg")
        bad = functions["search_domain"](query="anything", domain="randomblog.com")
        assert "error" in bad, "searching a non-allowed domain must be refused"
        seen_url = ok["results"][0]["url"]
        assert "error" in functions["preview_page"](url="https://evil.example.com/x")
        functions["preview_page"](url=seen_url)
        for _ in range(config.AGENT_MAX_SEARCHES + 2):
            last = functions["search_domain"](query="more", domain="mas.gov.sg")
        assert "error" in last, "search budget must run out"
        return json.dumps({"recommendations": [
            {"url": seen_url, "title": "Real one", "relevance": "high", "why_relevant": "transfer rules",
             "kind": "statistics"},
            {"url": "https://www.pdpc.gov.sg/invented-by-ai", "title": "Hallucinated", "relevance": "high"}],
            "notes": "ok"})

    config.LLM_PROVIDER, real = "gemini", llm.run_tool_agent
    llm.run_tool_agent = fake_agent
    try:
        result = discovery.discover("data_protection", "Singapore", progress=lambda m: None)
    finally:
        llm.run_tool_agent, config.LLM_PROVIDER = real, "offline"
    urls = [r["url"] for r in result["recommendations"]]
    assert result["method"] == "agent" and len(urls) == 1 and "invented" not in urls[0], urls
    assert any(t.get("status") == "dropped" for t in result["trace"]), "dropped links must be logged"
    assert result["recommendations"][0]["kind"] == "statistics", "the agent's 'statistics' label must be kept"
    print("✓ agent: other domains refused, budget enforced, invented link dropped and logged")


def test_gemini_loop_real_types():
    """Drive llm._gemini_agent with a fake client returning REAL google-genai response objects."""
    from google import genai
    from google.genai import types
    replies = [
        types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name="search_domain",
                                                        args={"query": "q", "domain": "pdpc.gov.sg"}))]))]),
        types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
            types.Part(text='{"recommendations": [], "notes": "done"}')]))]),
    ]
    sent = []

    class FakeModels:
        def generate_content(self, model, contents, config):
            sent.append(contents)
            return replies[len(sent) - 1]

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    real_client, genai.Client = genai.Client, FakeClient
    config.LLM_PROVIDER, llm.calls_made = "gemini", 0
    trace = []
    try:
        out = llm.run_tool_agent("sys", "task", discovery.TOOLS,
                                 {"search_domain": lambda query, domain: {"results": [{"url": "u"}]}}, 4, trace)
    finally:
        genai.Client, config.LLM_PROVIDER = real_client, "offline"
    fr = sent[1][-1].parts[0].function_response
    assert "done" in out and trace[0]["tool"] == "search_domain" and fr.name == "search_domain"
    print("✓ Gemini agent loop: real tool-call objects handled, result sent back, call logged")


def test_bedrock_loop():
    import boto3
    replies = [
        {"stopReason": "tool_use", "output": {"message": {"role": "assistant", "content": [
            {"toolUse": {"toolUseId": "t1", "name": "delete_everything", "input": {}}}]}}},
        {"stopReason": "end_turn", "output": {"message": {"role": "assistant", "content": [{"text": "{}"}]}}},
    ]
    calls = []

    class FakeBedrock:
        def converse(self, **kw):
            calls.append(kw)
            return replies[len(calls) - 1]

    real, boto3.client = boto3.client, lambda *a, **k: FakeBedrock()
    config.LLM_PROVIDER, llm.calls_made = "bedrock", 0
    trace = []
    try:
        llm.run_tool_agent("sys", "task", discovery.TOOLS, {}, 4, trace)
    finally:
        boto3.client, config.LLM_PROVIDER = real, "offline"
    assert trace[0]["status"] == "error" and "not allowed" in trace[0]["result_summary"]
    print("✓ Bedrock agent loop: a tool not on the menu is refused and logged")


def test_profile_and_checks():
    """Fake AI profile with one true date, one invented date and off-list items."""
    def fake_ask(system, prompt):
        return {"relevance": "High", "title": "Guidelines on SRF", "issue_date": "1 January 2024",
                "effective_date": "16 December 2024", "status": "In Force",
                "applies_to": "Banks and telcos", "key_requirements": ["Real-time alerts"],
                "areas_affected": ["Fraud operations", "Space travel"],
                "comparison": [{"question": "Who bears the loss", "answer": "Bank, if it breached a duty",
                                "evidence": "The responsible FI is expected to bear any loss", "page": 10},
                               {"question": "Favourite colour", "answer": "blue"}]}
    config.LLM_PROVIDER, real = "gemini", llm.ask_json
    llm.ask_json = fake_ask
    try:
        rec = pipeline.new_record("scams", ["Singapore"])
        pipeline.profile_sources(rec, [SRF], progress=lambda m: None)
    finally:
        llm.ask_json, config.LLM_PROVIDER = real, "offline"
    d = rec["documents"][0]
    p = d["profile"]
    codes = {f["code"] for f in d["flags"]}
    assert p["status"] == "in force" and p["areas_affected"] == ["Fraud operations"]
    assert [c["question"] for c in p["comparison"]] == ["Who bears the loss"] and p["comparison"][0]["evidence_found"]
    assert p["dates_verified"] == {"issue_date": False, "effective_date": True}
    assert "date_not_in_document" in codes, "an invented issue date must be flagged HIGH"
    print("✓ profile: invented date flagged HIGH; true date verified; off-list areas/questions dropped")
    return rec


def test_report_and_approval(rec):
    md = report.to_markdown(rec, topics.get("scams"))
    assert "## 1. Key dates" in md and "16 December 2024 ✓" in md and "DRAFT" in md
    try:
        pipeline.approve(rec, "Tester")
        raise AssertionError("approval must be blocked while a HIGH-flag document is unreviewed")
    except ValueError:
        pass
    pipeline.set_review(rec, rec["documents"][0]["id"], "accepted", "Issue date corrected manually", "Tester")
    pipeline.approve(rec, "Tester")
    assert "APPROVED" in report.to_markdown(rec, topics.get("scams"))
    print("✓ report & approval: dates tracker with ✓, approval blocked until HIGH flags reviewed")


def test_ask():
    def fake_ask(system, prompt):
        return {"answer": "Banks bear the loss if they breached a duty.", "found_in_document": True,
                "citations": [{"page": 10, "quote": "The responsible FI is expected to bear any loss"},
                              {"page": 3, "quote": "All banks must refund every scam victim in full"}]}
    config.LLM_PROVIDER, real = "gemini", llm.ask_json
    llm.ask_json = fake_ask
    try:
        a = ask.ask("Who bears the loss?", [SRF])
    finally:
        llm.ask_json, config.LLM_PROVIDER = real, "offline"
    assert [c["verified"] for c in a["citations"]] == [True, False]
    print("✓ ask: answers cite pages; a citation not in the document is marked unverified")


def test_keyword_fallback():
    sources.search_domain = _fake_search
    r = discovery.discover("data_protection", "Hong Kong", progress=lambda m: None)
    assert r["method"] == "keyword fallback" and r["recommendations"]
    print("✓ discovery without AI: keyword fallback still recommends documents")


def test_responsible_scraping():
    site = TMP / "site"
    (site / "private").mkdir(parents=True)
    (site / "robots.txt").write_text("User-agent: *\nDisallow: /private/\nCrawl-delay: 1\n")
    (site / "public.html").write_text("<html><body><article><p>" + "Data protection rules apply. " * 50 + "</p></article></body></html>")
    (site / "two.html").write_text((site / "public.html").read_text())
    (site / "private" / "secret.html").write_text("<p>secret</p>")
    (site / "botcheck.html").write_text("<html><body><p>Request unsuccessful. Incapsula incident ID: 1</p></body></html>")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(site), **kw)

        def do_GET(self):
            self.server.agents.append(self.headers.get("User-Agent"))
            super().do_GET()

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.agents = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    first = scraping.fetch(base + "/public.html")
    t0 = time.time()
    scraping.fetch(base + "/two.html")
    waited = time.time() - t0
    statuses = [scraping.fetch(base + p)["status"] for p in ("/public.html", "/private/secret.html", "/botcheck.html")]
    server.shutdown()
    assert first["status"] == "ok" and waited >= config.MIN_SECONDS_BETWEEN_REQUESTS - 0.1
    assert statuses == ["cached", "blocked_by_robots", "bot_check"], statuses
    assert all(a == config.USER_AGENT for a in server.agents)
    print(f"✓ scraping: robots.txt obeyed, waited {waited:.1f}s, cache used, bot-check detected, honest User-Agent")


def test_statistics_and_trends():
    """Fake AI lists figures from a statistics report - including one invented number."""
    lib = TMP / "lib"
    lib.mkdir(exist_ok=True)
    config.LIBRARY_DIR = lib
    (lib / "spf_stats.txt").write_text(
        "Scams and cybercrime statistics. There were 41,974 cases in 2025, down from 55,810 in 2024. "
        "Government official impersonation scams rose to 1,762 cases in 2025 from 1,504 in 2024. "
        "Investment scams fell to 4,210 cases in 2025 from 5,203 in 2024. Losses totalled $913.1 million. "
        + "The Police continue to work with banks, telcos and online platforms to disrupt scams. " * 12)
    src = {"id": "stats-1", "jurisdiction": "Singapore", "title": "SPF scam statistics 2025",
           "url": "https://www.police.gov.sg/x", "local_file": "spf_stats.txt", "kind": "statistics"}

    def fake_ask(system, prompt):
        if "extract statistics" in system:
            return {"points": [
                {"metric": "Number of cases", "category": "Total", "period": "2025", "value": "41,974", "unit": "cases",
                 "quote": "There were 41,974 cases in 2025"},
                {"metric": "Number of cases", "category": "Total", "period": "2024", "value": "55,810", "unit": "cases",
                 "quote": "down from 55,810 in 2024"},
                {"metric": "Number of cases", "category": "Government official impersonation", "period": "2025",
                 "value": "1,762", "unit": "cases", "quote": "rose to 1,762 cases in 2025"},
                {"metric": "Number of cases", "category": "Government official impersonation", "period": "2024",
                 "value": "1,504", "unit": "cases", "quote": "from 1,504 in 2024"},
                {"metric": "Number of cases", "category": "Investment", "period": "2025", "value": "4,210",
                 "unit": "cases", "quote": "Investment scams fell to 4,210 cases in 2025"},
                {"metric": "Number of cases", "category": "Investment", "period": "2024", "value": "9,999",
                 "unit": "cases", "quote": "Investment scams were 9,999 in 2024"}]}   # invented!
        return {"relevance": "high", "title": "SPF scam statistics 2025", "doc_type": "statistics", "status": "in force"}

    config.LLM_PROVIDER, real = "gemini", llm.ask_json
    llm.ask_json = fake_ask
    try:
        rec = pipeline.new_record("scams", ["Singapore"])
        pipeline.profile_sources(rec, [src], progress=lambda m: None)
    finally:
        llm.ask_json, config.LLM_PROVIDER = real, "offline"
    d = rec["documents"][0]
    bad = [p for p in d["stats"] if p["value_as_written"] == "9,999"][0]
    assert d["kind"] == "statistics" and not bad["verified"], "an invented figure must not be verified"
    t = {r["category"]: r for r in report.trend_rows(rec)}
    assert "Investment" not in t, "a trend must not be drawn from an unverified figure"
    assert t["Government official impersonation"]["direction"] == "up" and t["Total"]["direction"] == "down"
    assert round(t["Total"]["pct"], 1) == -24.8
    print("✓ statistics: invented figure excluded; trends computed by code (Total ▼ -24.8%, impersonation ▲)")
    return rec


def test_topic_reports(stats_rec):
    md = report.to_markdown(stats_rec, topics.get("scams"))
    order = [md.index(h) for h in ("## 1. Key dates", "## 2. Trends", "## 3. Compare jurisdictions",
                                   "## 4. Document profiles")]
    assert order == sorted(order), "scams: key dates -> trends -> comparison -> profiles"
    empty = pipeline.new_record("data_protection", ["Singapore"])
    assert report.visible_sections(empty, topics.get("data_protection")) == ["key_dates", "comparison", "profiles"], \
        "data protection hides Trends when none were found"
    assert topics.get("financial_crime")["report_sections"][:3] == ["key_dates", "obligations", "trends"]
    print("✓ reports: each topic has its own section order; Trends hidden for data protection when none found")


def test_live_run_lessons():
    """Bugs from the first live run, now locked in by tests."""
    import models
    # 1. The AI's odd shapes (null, lists, '5-6' pages) must not throw the whole profile away.
    prof = models.Profile(**{"issuer": None, "covers": ["phishing", "malware"], "exclusions": None,
                             "transition_notes": {"phase 1": "2025"}, "extra_key": 1,
                             "comparison": [{"question": "Who bears the loss", "answer": None, "page": "5-6"}, None]})
    assert prof.covers == "phishing; malware" and prof.issuer == "" and prof.comparison[0].page == 5
    # 2. Same thing -> same name, so series line up across documents.
    pack = topics.get("scams")
    def tidy(metric, category, unit):
        return stats.tidy({"metric": metric, "category": category, "unit": unit, "period": "2024",
                           "value": 1, "jurisdiction": "Singapore", "source_id": "x"}, pack)
    a, b = tidy("number of reported scam cases", "Scam", ""), tidy("Number of cases", "Total", "cases")
    assert (a["metric"], a["category"], a["unit"]) == (b["metric"], b["category"], b["unit"]) == ("number of cases", "Total", "cases")
    assert tidy("amount lost", "Phishing Scams", "S$")["unit"] == "SGD"
    assert tidy("amount lost", "Phishing Scams", "S$")["category"] == "Phishing"
    share = tidy("amount lost", "Cryptocurrency", "%")
    assert share["metric"] == "share of amount lost" and not share["headline"]
    # 3. "1H 2026" is a half-year; a % change of a % is shown in points.
    assert stats.period_key("1H 2026") == ("half-year", 2026, 1)
    row = {"unit": "%", "change": 17.5, "pct": None, "direction": "up"}
    assert stats.arrow(row) == "▲ +17.5 pts"
    # 4. Second live run: casing, period labels, revised figures, statistics aren't rules.
    assert tidy("number of cases", "Fake Friend Call", "")["category"] == tidy("number of cases", "Fake friend call", "")["category"]
    assert stats.tidy({"metric": "number of cases", "category": "Total", "unit": "", "period": "January to June 2024",
                       "value": 1, "jurisdiction": "Singapore", "source_id": "x"}, pack)["period"] == "H1 2024"
    def pt(src, period, value):
        return {"metric": "number of cases", "category": "Total", "unit": "cases", "period": period,
                "value": value, "verified": True, "jurisdiction": "Singapore", "source_id": src}
    pts = [pt("brief-2024", "H1 2023", 22000), pt("brief-2024", "H1 2024", 26587),      # older report
           pt("brief-2025", "H1 2024", 26563), pt("brief-2025", "H1 2025", 19665)]      # newer report revises H1 2024
    line = stats.series(pts)[("Singapore", "number of cases", "cases", "half-year")]["Total"]
    assert [v for _, _, v, _ in line] == [22000, 26563, 19665], "the newer report's figure must win"
    rev = stats.revisions(pts)
    assert len(rev) == 1 and rev[0]["charted"] == 26563 and rev[0]["other"] == 26587
    rec = pipeline.new_record("scams", ["Singapore"])
    rec["documents"] = [{"id": "s", "jurisdiction": "Singapore", "title": "Brief", "kind": "statistics", "stats": pts,
                         "profile": {"title": "Brief", "status": "in force", "comparison": [
                             {"question": "Which scams are covered", "answer": "lots"}]}, "review": None}]
    assert report.tracker_rows(rec)[0]["Status"] == "n/a"
    assert not report.comparison(rec, ["Which scams are covered"])["Which scams are covered"], \
        "a statistics brief must not answer the liability comparison"
    # 5. Third live run: broken JSON retried; side breakdowns; duplicate revisions; latest period first.
    calls, real_text, real_provider = [], llm._gemini_text, config.LLM_PROVIDER
    llm._gemini_text = lambda s, p, json_mode: (calls.append(p), '{"broken": ' if len(calls) == 1 else '{"ok": true}')[1]
    config.LLM_PROVIDER = "gemini"
    try:
        assert llm.ask_json("retry-test system", "retry-test prompt") == {"ok": True} and len(calls) == 2
        assert "not valid JSON" in calls[1]
    finally:
        llm._gemini_text, config.LLM_PROVIDER = real_text, real_provider
    assert tidy("amount lost", "Per case", "SGD")["headline"] is False
    assert tidy("number of cases", "Via social media", "")["metric"] == "number of cases by contact channel"
    assert tidy("number of cases", "Total Scam and Cybercrime Cases", "")["category"] == "Total incl. cybercrime"
    assert len(stats.revisions(pts + [pt("brief-2024", "H1 2024", 26587)])) == 1, "a figure listed twice is one revision"
    old = [pt("brief-2024", "H1 2023", 100), pt("brief-2024", "H1 2024", 5)]
    for o in old:
        o["category"] = "Malware"
    assert tidy("number of cases", "Social media platforms contact method", "")["category"] == \
        tidy("number of cases", "Via social media", "")["category"] == "Social media"
    assert tidy("number of cases via online shopping platforms", "Total", "")["metric"] == "number of cases by contact channel"
    assert tidy("number of cases", "Social media impersonation", "")["metric"] == "number of cases", \
        "a scam TYPE that mentions social media is not a contact channel"
    big = stats.revisions([pt("new", "2024", 1.11e9), pt("old", "2024", 151.3e6)])
    assert big and big[0]["check"], "a >20% gap must be flagged for checking"
    first = stats.trends(pts + old)[0]
    assert first["latest_period"] == "H1 2025", "the newest comparison leads, not an older one"
    doc = {"id": "r", "jurisdiction": "Singapore", "key": "S1", "pages": [
        "Intro text about the framework. " * 5,
        "Duties of the responsible FI: the responsible FI must impose a cooling-off period of 12 hours. "
        + "The responsible FI must also send real-time notifications for outgoing transactions. " * 4]}
    first_pass = models.Profile(relevance="high", comparison=[{"question": "Who bears the loss", "answer": "The FI."}])
    seen = []
    def fake(system, prompt):
        seen.append(prompt)
        return {"comparison": [{"question": "Duties on banks", "answer": "Impose a 12-hour cooling-off period.",
                                "evidence": "must impose a cooling-off period", "page": 2},
                               {"question": "Invented question", "answer": "x"}]}
    real_ask, llm.ask_json = llm.ask_json, fake
    try:
        filled = profiler.fill_comparison(doc, first_pass, pack)
    finally:
        llm.ask_json = real_ask
    qs = [c.question for c in filled.comparison]
    assert "Duties on banks" in qs and "Invented question" not in qs and "Who bears the loss" not in seen[0].split("\n")[0]
    assert "cooling-off" in seen[0], "the focused pass must include the passage about duties"
    rec2 = pipeline.new_record("scams", ["Singapore"])
    rec2["documents"] = [{"id": "st", "jurisdiction": "Singapore", "title": "Brief", "kind": "statistics", "stats": [],
                          "profile": {"relevance": "not relevant"}, "review": None}]
    assert report.included(rec2), "'not relevant' to the rules must not hide a statistics brief"
    # UK periods (live run: ONS "year ending March 2025" figures were never charted).
    assert stats.period_key("year ending March 2025") == ("year to Mar", 2025, 0)
    assert stats.period_key("2024/25") == ("financial year", 2025, 0)
    uk = [{"metric": "number of incidents", "category": "Fraud", "unit": "", "period": per, "value": v,
           "verified": True, "jurisdiction": "United Kingdom", "source_id": "ons"}
          for per, v in [("year ending March 2024", 3.2e6), ("year ending March 2025", 4.2e6)]]
    uk_row = stats.trends(uk)[0]
    assert round(uk_row["pct"]) == 31, "matches the ONS headline (+31%)"
    assert tidy("number of cases", "Tiktok", "")["metric"] == "number of cases by contact channel"
    # Australia: reporting sources are not scam types; "Combined losses" is the total; "On X" is a channel.
    assert tidy("amount lost", "Scamwatch", "AUD")["metric"] == "amount lost by reporting source"
    assert tidy("amount lost", "Combined losses", "AUD")["category"] == "Total"
    assert tidy("number of cases", "On Carousell", "")["category"] == "Carousell"
    au = stats.tidy({"metric": "amount lost", "category": "Remote access", "unit": "SGD", "period": "2025",
                     "value": 1, "jurisdiction": "Australia", "source_id": "x"}, pack)
    assert au["unit"] == "AUD", "another country's dollar in an Australian report is the AI's slip"
    assert tidy("number of cases", "Adjustments", "")["category"] == "Adjustment"
    import models
    old_news = models.Profile(status="upcoming", effective_date="1 September 2025")
    assert profiler._fill_status(old_news).status == "in force", "status follows today's date"
    assert profiler._fill_status(models.Profile(status="consultation", effective_date="1 September 2025")).status == "consultation"
    assert dates.stated_in("31 December 2021", "comes into operation on 31/12/2021"), "day-first numeric dates count"
    assert not dates.stated_in("31 December 2021", "comes into operation on 30/12/2021")
    cell = report.cell_text([{"answer": "3 days.", "ref": "SG-4", "evidence_found": False},
                             {"answer": "3 days.", "ref": "SG-5", "evidence_found": False},
                             {"answer": "Notify within 3 calendar days.", "ref": "SG-1", "evidence_found": True}])
    assert cell.startswith("Notify within 3 calendar days. [SG-1] ✓") and "[SG-4, SG-5] ⚠️ quote not found" in cell
    assert not reading.injection_signals("An organisation may act as a data intermediary for another.")
    print("✓ live-run lessons: tolerant profiles, consistent names/currencies/periods, revised figures "
          "shown (newer wins), statistics kept out of rule tables")


def test_manual_downloads():
    """Blocked sources get a suggested file name; a file saved under it is used automatically."""
    lib = TMP / "lib_manual"
    lib.mkdir(exist_ok=True)
    config.LIBRARY_DIR = lib
    src = {"id": "x", "jurisdiction": "Hong Kong", "title": "PCPD Guidance on Model Clauses (Cross-border)",
           "url": "https://www.pcpd.org.hk/english/files/GN_crossborder_e.pdf", "kind": "rule"}
    name = sources.suggested_filename(src)
    assert name.startswith("HK_pcpd-guidance-on-model-clauses-cross-border_") and name.endswith(".pdf")
    rec = pipeline.new_record("data_protection", ["Hong Kong"])
    rec["access_log"] = [{**src, "status": "bot_check", "reason": "blocked", "tier": 1}]
    todo = pipeline.manual_downloads_needed(rec)
    assert len(todo) == 1 and todo[0]["suggested_file"] == name
    # The human saves the file under the suggested name (title wording may differ next run - the link decides).
    (lib / name).write_text("Personal Data (Privacy) Ordinance guidance. Transfers of personal data outside "
                            "Hong Kong should use the recommended model clauses. " * 20)
    doc = sources.get_document({**src, "title": "Slightly different title next run"})
    assert doc["status"] == "library" and doc.get("manual_copy") and doc["local_file"] == name
    # The "Check which links can be read" button: readable / download by hand / already have a copy.
    real_fetch = scraping.fetch
    scraping.fetch = lambda url: {"status": "bot_check", "reason": "blocked"} if "mas" in url else {"status": "ok"}
    try:
        blocked = sources.check_access({"jurisdiction": "Singapore", "title": "SRF", "url": "https://www.mas.gov.sg/srf"})
        fine = sources.check_access({"jurisdiction": "Singapore", "title": "Guide", "url": "https://www.pdpc.gov.sg/g"})
        have = sources.check_access(src)
    finally:
        scraping.fetch = real_fetch
    assert blocked["state"] == "manual" and blocked["file"].startswith("SG_srf_")
    assert fine["state"] == "ok" and have["state"] == "have_copy"
    (lib / "HK_scanned_000000.pdf").write_text("Page 1")          # a near-empty file must not be profiled
    thin = sources.get_document({"id": "t", "jurisdiction": "Hong Kong", "title": "t", "local_file": "HK_scanned_000000.pdf"})
    assert thin["status"] == "too_little_text" and not thin["pages"]
    rec3 = pipeline.new_record("data_protection", ["Hong Kong"])
    pipeline.profile_sources(rec3, [src, {**src, "id": "lib-copy", "local_file": name}], progress=lambda m: None)
    assert len(rec3["documents"]) == 1, "a link and its uploaded copy must be read once"
    assert rec3["access_log"][0]["status"] == "library", "the saved copy wins over the blocked website"
    # Same document found at a different link next run: recognised, not asked for again.
    assert sources.same_document({"jurisdiction": "Hong Kong", "title": "New Guidance on Direct Marketing", "url": "a"},
                                 {"jurisdiction": "Hong Kong", "title": "New Guidance on Direct Marketing (PCPD)", "url": "b"})
    assert not sources.same_document({"jurisdiction": "Hong Kong", "title": "Data Breach Handling", "url": "a"},
                                     {"jurisdiction": "Hong Kong", "title": "Cross-Border Data Transfer", "url": "b"})
    assert report.cell_text([{"answer": "", "ref": "SG-1"}]) == "Not stated", "an empty answer is no answer"
    print("✓ manual downloads: links checked up front; blocked sources get a file name; saved copies matched by link")


def test_scanned_pdf_ocr():
    """A scanned PDF (no text layer) is transcribed by the AI in chunks, checked and flagged."""
    import io
    import ocr
    from pypdf import PdfWriter
    lib = TMP / "lib_ocr"
    lib.mkdir(exist_ok=True)
    config.LIBRARY_DIR = lib
    writer = PdfWriter()
    for _ in range(8):                      # 8 blank pages = a "scan" with no text layer
        writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    (lib / "IN_dpdp-act_scan.pdf").write_bytes(buf.getvalue())
    calls = []
    def fake_chunk(pdf_chunk):              # stands in for Gemini; page 4 of the 2nd chunk comes back empty
        n = len(__import__("pypdf").PdfReader(io.BytesIO(pdf_chunk)).pages)
        calls.append(n)
        return "\n".join(f"=== PAGE {i} ===\nThe Digital Personal Data Protection Act, 2023. Section {i}. "
                         + "A Data Fiduciary shall protect personal data in its possession. " * 4
                         for i in range(1, n + 1) if not (len(calls) == 2 and i == 2))
    ocr._CACHE = TMP / "ocr_cache"
    ocr._CACHE.mkdir(exist_ok=True)
    real, real_provider, real_key = ocr._transcribe_chunk, config.LLM_PROVIDER, config.GEMINI_API_KEY
    ocr._transcribe_chunk, config.LLM_PROVIDER, config.GEMINI_API_KEY = fake_chunk, "gemini", "test-key"
    try:
        doc = sources.get_document({"id": "dp", "jurisdiction": "India", "title": "DPDP Act",
                                    "local_file": "IN_dpdp-act_scan.pdf"})
        again = sources.get_document({"id": "dp", "jurisdiction": "India", "title": "DPDP Act",
                                      "local_file": "IN_dpdp-act_scan.pdf"})
    finally:
        ocr._transcribe_chunk, config.LLM_PROVIDER, config.GEMINI_API_KEY = real, real_provider, real_key
    assert calls == [6, 2], "sent in small chunks"
    assert doc["status"] == "library" and len(doc["pages"]) == 8 and "Data Fiduciary" in doc["pages"][0]
    assert doc["ocr"]["pages_missing"] == [8], "a page the AI skipped is reported by code"
    assert again["pages"] == doc["pages"] and calls == [6, 2], "cached: the same file is never paid for twice"
    entry = {"profile": {}, "tier": 1, "method": "llm", "ocr": doc["ocr"]}
    checks.check_document(entry, " ".join(doc["pages"]), [])
    assert any(f["code"] == "read_by_ai_ocr" for f in entry["flags"]), "OCR-read documents are flagged for review"
    # A chunk that comes back EMPTY (e.g. RECITATION) is retried one page at a time, and the reason kept.
    w2 = PdfWriter()
    for _ in range(3):
        w2.add_blank_page(width=595, height=842)
    b2 = io.BytesIO()
    w2.write(b2)
    def picky(pdf_chunk):
        n = len(__import__("pypdf").PdfReader(io.BytesIO(pdf_chunk)).pages)
        return ("", "RECITATION") if n > 1 else ("=== PAGE 1 ===\n" + "Guidance on data breach handling. " * 12, "STOP")
    ocr._transcribe_chunk, config.LLM_PROVIDER, config.GEMINI_API_KEY = picky, "gemini", "test-key"
    try:
        r = ocr.read_scanned_pdf(b2.getvalue())
    finally:
        ocr._transcribe_chunk, config.LLM_PROVIDER, config.GEMINI_API_KEY = real, real_provider, real_key
    assert all("data breach" in pg for pg in r["pages"]) and "RECITATION" in r["problems"][0]
    print("✓ scanned PDFs: AI transcribes in small chunks, missing pages reported, empty replies retried "
          "page by page (reason kept), cached, flagged for review")


if __name__ == "__main__":
    test_dates()
    test_reading_boosts_dates()
    test_agent_guardrails()
    test_gemini_loop_real_types()
    test_bedrock_loop()
    record = test_profile_and_checks()
    test_report_and_approval(record)
    test_ask()
    test_keyword_fallback()
    stats_record = test_statistics_and_trends()
    test_topic_reports(stats_record)
    test_live_run_lessons()
    test_manual_downloads()
    test_scanned_pdf_ocr()
    test_responsible_scraping()
    print("\nAll offline tests passed.")