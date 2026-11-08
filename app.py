"""
app.py - RegRadar's screen (Streamlit).   Run:  streamlit run app.py

REMINDER: Streamlit re-runs this whole script on every click. Anything that must
survive between clicks lives in st.session_state (here called `ss`).

THE TABS ARE BUILT FROM THE TOPIC'S REPORT ORDER (topics.py -> report_sections)
  ① Find sources     agent recommends rules + statistics documents; YOU tick them
  then, per topic, e.g. for scams:  Key dates -> Trends -> Compare
                       data protection: Key dates -> Compare -> (Trends if found)
                       financial crime: Key dates -> Obligations -> Trends -> Compare
  then always:       Ask · Report & approval · Audit trail · How it works

Each view is a function (render_...) so the tabs can be put in any order.
"""
import json
import re
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import ask
import checks
import config
import dates
import discovery
import llm
import pipeline
import report
import sources
import stats
import topics

st.set_page_config(page_title="RegRadar", page_icon="🛰️", layout="wide")
ss = st.session_state
for key, default in {"discovery": {}, "extra_domains": {}, "manual": [], "record": None,
                     "topic_prev": None, "discovery_calls": 0, "last_answer": None,
                     "access": {}, "upload_round": 0, "manual_result": []}.items():
    ss.setdefault(key, default)

SEVERITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡", "info": "🔵"}
CIRCLED = "②③④⑤⑥⑦⑧⑨⑩"


def md(text) -> str:
    """Escape '$' so amounts like S$50,000 aren't rendered as maths."""
    return str(text or "").replace("$", "\\$")


def dark_mode() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


# Chart colours: a validated categorical palette, used in FIXED order (never cycled),
# max 5 series at once. Light and dark steps of the same hues. (See README: charts.)
PALETTE = {False: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
           True: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]}
# Dumbbell (previous vs latest): two shades of ONE blue - the fainter one = previous.
SHADES = {False: ["#86b6ef", "#1c5cab"], True: ["#2a78d6", "#9ec5f4"]}
# Text marks wear TEXT colours (never a series colour), light vs dark surface.
TEXT = {False: "#52514e", True: "#c3c2b7"}


def trace_table(trace: list[dict]) -> pd.DataFrame:
    """The agent's tool calls as a table. 'turn' is usually a number but can be "check" or
    "limit" (guardrail rows), and 'input' is a dict - so both are shown as text. Mixed types
    in one column make Streamlit print a long ArrowInvalid warning."""
    df = pd.DataFrame(trace)
    for col in ("turn", "input"):
        if col in df:
            df[col] = df[col].astype(str)
    return df


def spread_labels(values: list[float], min_gap: float) -> list[float]:
    """Nudge end-of-line labels apart so close values don't print on top of each other."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    placed = list(values)
    for a, b in zip(order, order[1:]):
        if placed[b] - placed[a] < min_gap:
            placed[b] = placed[a] + min_gap
    return placed

# ===========================================================================
# Sidebar
# ===========================================================================
with st.sidebar:
    st.title("🛰️ RegRadar")
    st.caption("External driver research for internal audit")
    topic_id = st.selectbox("Topic", list(topics.TOPICS), format_func=lambda t: topics.TOPICS[t]["name"],
                            index=list(topics.TOPICS).index(topics.DEFAULT_TOPIC))
    pack = topics.get(topic_id)
    if ss.topic_prev != topic_id:  # new topic -> start fresh
        ss.discovery, ss.manual, ss.record, ss.topic_prev, ss.last_answer = {}, [], None, topic_id, None
    st.caption(pack["description"])
    jurisdictions = st.multiselect("Jurisdictions", list(pack["domains"]), default=pack["default_jurisdictions"])
    reviewer = st.text_input("Your name (reviewer)")
    st.markdown(f"**AI:** {llm.describe()}")
    if config.LLM_PROVIDER == "offline":
        st.info("No AI key found: discovery uses keyword search, profiles are rough and trends need AI. "
                "Add GEMINI_API_KEY to .env.")
    runs = pipeline.list_runs()
    if runs:
        chosen_run = st.selectbox("Open a previous run", ["—"] + runs)
        if chosen_run != "—" and st.button("Open run"):
            ss.record = pipeline.load(chosen_run)
            st.rerun()

rec = ss.record
rec_pack = topics.get(rec["topic"]) if rec else pack


# ===========================================================================
# ① FIND SOURCES
# ===========================================================================
def render_find_sources():
    st.subheader("Find documents")
    st.write("The agent searches **only** the domains below for **rules** and **statistics** and recommends "
             "documents. **You decide** which ones are read.")
    for j in jurisdictions:
        doms = topics.domains_for(topic_id, j, ss.extra_domains.get(j))
        note = pack.get("language_notes", {}).get(j)
        st.markdown(f"**{j}:** {', '.join(doms)}" + (f"  \n<small>🌐 {note}</small>" if note else ""),
                    unsafe_allow_html=True)
    with st.expander("➕ Add a domain for the agent to search (e.g. mas.gov.sg)"):
        c1, c2 = st.columns([1, 2])
        dj = c1.selectbox("Jurisdiction", jurisdictions or list(pack["domains"]), key="dom_j")
        dv = c2.text_input("Domain or any link on that site", key="dom_v")
        if st.button("Add domain") and dv.strip():
            ss.extra_domains.setdefault(dj, []).append(sources.clean_domain(dv))
            st.rerun()

    if st.button("🤖 Find documents", type="primary", disabled=not jurisdictions):
        llm.calls_made = 0
        with st.status("Discovery agent at work...", expanded=True) as status:
            for j in jurisdictions:
                ss.discovery[j] = discovery.discover(topic_id, j, ss.extra_domains.get(j), progress=st.write)
            status.update(label="Recommendations ready - tick what to read below", state="complete")
        ss.discovery_calls = llm.calls_made

    # Before reading anything: which recommended links can the app read, and which need a
    # human download? (The agent rarely previews pages, so we check explicitly.)
    all_recs = [r for j in jurisdictions for r in (ss.discovery.get(j) or {}).get("recommendations", [])]
    unchecked = [r for r in all_recs if r["url"] not in ss.access]
    if all_recs:
        label = (f"🔍 Check which links can be read ({len(unchecked)} to check)" if unchecked
                 else "🔍 All links checked - check again")
        if st.button(label, help="Tries each link politely (robots.txt, rate limit). Readable pages are cached, "
                                 "so reading them later is instant. Takes a few seconds per site."):
            todo = unchecked or all_recs
            bar = st.progress(0.0, text="Checking links...")
            for i, r in enumerate(todo, start=1):
                ss.access[r["url"]] = sources.check_access(r)
                bar.progress(i / len(todo), text=f"Checked {i}/{len(todo)}: {r['title'][:60]}")
            st.rerun()

    def access_cells(r: dict) -> tuple[str, str]:
        if lib := sources.library_match(r, topic_id):                   # same link or same title, saved before
            return "📂 in your library (read from there)", lib["local_file"]
        if copy := sources.find_manual_copy(r["url"]):                 # already downloaded by hand
            return "📂 your copy in library", copy.name
        a = ss.access.get(r["url"])
        if a:
            return a["label"], a["file"]
        # Already tried while reading? Then we know the answer without checking again.
        rec_now = ss.get("record")
        if rec_now and rec_now.get("topic") == topic_id:
            tried = [x for x in rec_now["access_log"] if x.get("url") == r["url"]]
            if tried:
                status = tried[-1].get("status")
                if status in sources.FAILED_STATUSES:
                    return "⬇️ download by hand", tried[-1].get("suggested_file") or sources.suggested_filename(r)
                if status in ("ok", "cached", "library"):
                    return "✅ read", ""
        if r.get("needs_manual_download"):                              # the agent's preview said so
            return "⬇️ download by hand", sources.suggested_filename(r)
        return "not checked yet", ""

    chosen = []
    for j in jurisdictions:
        result = ss.discovery.get(j)
        if not result:
            continue
        n_stats = sum(1 for r in result["recommendations"] if r.get("kind") == "statistics")
        st.markdown(f"#### {j} — {len(result['recommendations'])} recommended ({n_stats} statistics) "
                    f"<small>({result['method']})</small>", unsafe_allow_html=True)
        if result.get("notes"):
            st.caption(f"Agent's note: {md(result['notes'])}")
        recs = result["recommendations"]
        if recs:
            table = pd.DataFrame([{
                # Already in the library? Then the library row below is read instead - no re-upload needed.
                "read": r["relevance"] == "high" and not sources.library_match(r, topic_id),
                "can the app read it?": access_cells(r)[0],
                "kind": "📈 statistics" if r.get("kind") == "statistics" else "📜 rule",
                "relevance": r["relevance"], "title": r["title"], "link": r["url"],
                "save file as": access_cells(r)[1], "why": r.get("why", ""),
                "dates seen": r.get("dates_seen", "")} for r in recs])
            edited = st.data_editor(table, hide_index=True, width="stretch", key=f"rec-{topic_id}-{j}",
                                    disabled=[c for c in table.columns if c != "read"],
                                    column_config={"read": st.column_config.CheckboxColumn("Read?"),
                                                   "link": st.column_config.LinkColumn("Link")})
            chosen += [r for r, row in zip(recs, edited.to_dict("records")) if row["read"]]
        with st.expander("Agent's working (every search and preview)"):
            st.dataframe(trace_table(result["trace"]), hide_index=True, width="stretch")

    st.divider()
    st.markdown("**Library & links added by hand** — for sites that block bots, or documents the agent missed.")
    lib = sources.library_sources(topic_id, jurisdictions) + [m for m in ss.manual if m["jurisdiction"] in jurisdictions]
    if lib:
        lib_table = pd.DataFrame([{"read": True, "kind": "📈 statistics" if l.get("kind") == "statistics" else "📜 rule",
                                   "jurisdiction": l["jurisdiction"], "title": l["title"],
                                   "origin": l.get("origin", "")} for l in lib])
        lib_edit = st.data_editor(lib_table, hide_index=True, width="stretch", key=f"lib-{topic_id}",
                                  disabled=["kind", "jurisdiction", "title", "origin"],
                                  column_config={"read": st.column_config.CheckboxColumn("Read?")})
        chosen += [l for l, row in zip(lib, lib_edit.to_dict("records")) if row["read"]]
    c1, c2 = st.columns(2)
    with c1, st.expander("📎 Upload a document"):
        up = st.file_uploader("PDF, HTML or text", type=["pdf", "html", "htm", "txt"])
        uj = st.selectbox("Jurisdiction", list(pack["domains"]), key="up_j")
        ut = st.text_input("Title", key="up_t")
        uu = st.text_input("Original link (if any)", key="up_u")
        uo = st.checkbox("Official regulator/government document", key="up_o")
        uk = st.radio("Kind", ["rule", "statistics"], horizontal=True, key="up_k")
        if st.button("Add to library", disabled=up is None):
            sources.add_to_library(up.name, up.getvalue(), topic_id, uj, ut, uu, uo, reviewer, kind=uk)
            st.rerun()
    with c2, st.expander("🔗 Paste a link"):
        lj = st.selectbox("Jurisdiction", list(pack["domains"]), key="ln_j")
        lu = st.text_input("Link", key="ln_u")
        lt = st.text_input("Title (optional)", key="ln_t")
        lk = st.radio("Kind", ["rule", "statistics"], horizontal=True, key="ln_k")
        if st.button("Add link") and lu.strip():
            ss.manual.append({**sources.manual_link(lu.strip(), lj, lt), "kind": lk})
            st.rerun()

    st.divider()
    if len(chosen) > config.MAX_DOCUMENTS_PER_RUN:
        st.warning(f"⚠️ {len(chosen)} ticked, but one run reads at most {config.MAX_DOCUMENTS_PER_RUN} "
                   f"(cost and review limit). The last {len(chosen) - config.MAX_DOCUMENTS_PER_RUN} would be skipped - "
                   "untick the ones you need least.")
    if st.button(f"▶ Read and profile {len(chosen)} document(s)", type="primary", disabled=not chosen):
        llm.calls_made = 0
        new = pipeline.new_record(topic_id, jurisdictions)
        new["discovery"] = [ss.discovery[j] for j in jurisdictions if j in ss.discovery]
        with st.status("Reading and profiling...", expanded=True) as status:
            pipeline.profile_sources(new, chosen, progress=st.write)
            new["llm"]["calls"] += ss.discovery_calls
            pipeline.save(new)
            status.update(label="Done - see the next tabs", state="complete")
        ss.record = new
        st.rerun()

    if ss.get("record") and ss.record["topic"] == topic_id:
        render_manual_downloads(ss.record)


def render_manual_downloads(record: dict):
    """Sources the app couldn't read itself: open the link, save the file, upload it here.

    Sites that block bots are never worked around (responsible scraping). Instead the
    human downloads the file - and the app makes that quick: it says WHICH files, WHY,
    and WHAT to call them, then reads them straight into the current run."""
    todo = pipeline.manual_downloads_needed(record)
    # What happened to the files uploaded last time (shown once, right after reading them).
    for ok, msg in ss.manual_result:
        (st.success if ok else st.error)(msg)
    ss.manual_result = []
    if not todo:
        return
    st.divider()
    st.markdown(f"### ⬇️ Manual downloads needed ({len(todo)})")
    st.caption("These sites block automated reading or returned no readable text. Open each link in your browser, "
               "save the file, then upload it below - the app files it under the right country, topic and kind. "
               f"Or save it with the suggested name in `{config.LIBRARY_DIR.resolve()}` and it is picked up "
               "automatically on the next run.")
    ready = []
    for a in todo:
        with st.container(border=True):
            kind = "📈 statistics" if a.get("kind") == "statistics" else "📜 rule"
            st.markdown(f"**{md(a['title'])}** · {a['jurisdiction']} · {kind}  \n"
                        f"<small>Why: {md(a['status'])} - {md((a.get('reason') or '')[:140])}</small>",
                        unsafe_allow_html=True)
            c1, c2 = st.columns([1, 2])
            c1.link_button("Open link ↗", a["url"])
            c2.code(a["suggested_file"], language=None)       # has a copy button
            up = st.file_uploader("Upload the downloaded file", type=["pdf", "html", "htm", "txt"],
                                  key=f"man-{ss.upload_round}-{sources.link_fingerprint(a['url'])}",
                                  label_visibility="collapsed")
            if up is not None:
                ext = Path(up.name).suffix.lower() or ".pdf"
                name = Path(a["suggested_file"]).with_suffix(ext).name      # keep the real file type
                entry = sources.add_to_library(name, up.getvalue(), record["topic"], a["jurisdiction"], a["title"],
                                               a["url"], official=a.get("tier") == 1, added_by=reviewer,
                                               kind=a.get("kind") or "rule")
                ready.append({**entry, "origin": "library"})
                st.caption(f"✓ Saved as `{name}`")
    if ready and st.button(f"▶ Read {len(ready)} uploaded file(s) into this run", type="primary"):
        with st.status("Reading and profiling uploaded files...", expanded=True) as status:
            pipeline.profile_sources(record, ready, progress=st.write)
            status.update(label="Done", state="complete")
        # Report each file's outcome, then clear the upload boxes so the button goes away.
        have = {d.get("url") for d in record["documents"]}
        latest = {a.get("url"): a for a in record["access_log"]}
        ss.manual_result = [
            (True, f"✓ Added: {e['title']}") if e["url"] in have else
            (False, f"✗ Not added: {e['title']} - {latest.get(e['url'], {}).get('reason') or 'could not be read'}")
            for e in ready]
        ss.upload_round += 1
        st.rerun()


# ===========================================================================
# KEY DATES (+ document profiles and review)
# ===========================================================================
def render_key_dates():
    rows = report.tracker_rows(rec)
    soon = [r for r in rows if r["_days"] is not None and 0 <= r["_days"] <= config.EFFECTIVE_SOON_DAYS]
    m = st.columns(4)
    m[0].metric("Documents", len(rows))
    tried = {a.get("url") or a.get("id") for a in rec["access_log"]}
    failed = len(pipeline.manual_downloads_needed(rec))
    hidden = len(rec["documents"]) - len(rows)
    skipped = sum(1 for n in rec["notes"] if "were read (limit)" in str(n.get("note", "")))
    m[0].caption(f"{len(tried)} sources tried · {len(rec['documents'])} read · {failed} couldn't be read"
                 + (f" · {hidden} hidden (rejected / not relevant)" if hidden else "")
                 + (" · some skipped (over the 15 limit)" if skipped else ""))
    m[1].metric(f"Effective within {config.EFFECTIVE_SOON_DAYS} days", len(soon))
    m[2].metric("Dates verified in document",
                sum(1 for d in rec["documents"] for v in d["profile"].get("dates_verified", {}).values() if v))
    m[3].metric("High flags to review", len(pipeline.unreviewed_high(rec)))
    if missing := pipeline.manual_downloads_needed(rec):
        st.warning(f"⬇️ {len(missing)} source(s) couldn't be read automatically - see **① Find sources → "
                   "Manual downloads needed** for the links and the file names to use.")
    for n in rec.get("notes", []):
        st.caption(f"ℹ️ {md(n['note'])}")

    # Timeline: one dot per effective date, rows = jurisdictions, dashed line = today.
    points = []
    for r in rows:
        parsed = dates.parse(r["Effective"].replace(" ✓", ""))
        if parsed:
            points.append({"Jurisdiction": r["Jurisdiction"], "Document": r["Document"], "Effective": r["Effective"],
                           "When": r["When"], "Status": r["Status"], "date": parsed[0].isoformat()})
    if points:
        base = alt.Chart(pd.DataFrame(points)).encode(x=alt.X("date:T", title="Effective date"),
                                                      y=alt.Y("Jurisdiction:N", title=None))
        dots = base.mark_circle(size=140, opacity=0.9, color=PALETTE[dark_mode()][0]).encode(
            tooltip=["Document", "Effective", "When", "Status"])
        today = pd.DataFrame({"date": [pd.Timestamp.today().normalize()], "t": ["today"]})
        rule = alt.Chart(today).mark_rule(strokeDash=[4, 4], color="gray").encode(x="date:T")
        label = alt.Chart(today).mark_text(align="left", dx=4, dy=-6, color=TEXT[dark_mode()]).encode(
            x="date:T", text="t:N")
        st.altair_chart((rule + label + dots).properties(height=60 + 45 * len({p["Jurisdiction"] for p in points})),
                        width="stretch")
    st.dataframe(pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]),
                 hide_index=True, width="stretch")
    st.caption("✓ = date found in the document by an automated check. ⏰ = takes effect soon.")

    st.subheader("Document profiles")
    refs = report.refs(rec)
    by_id = {d["id"]: d for d in rec["documents"]}
    order = [r["_id"] for r in rows] + [d["id"] for d in rec["documents"] if d["id"] not in {r["_id"] for r in rows}]
    for doc_id in order:
        render_profile(by_id[doc_id], refs)


def render_profile(d: dict, refs: dict):
    p = d["profile"]
    icons = "".join(SEVERITY_ICON[f["severity"]] for f in d.get("flags", []))
    kind = " 📈" if d.get("kind") == "statistics" else ""
    with st.expander(f"[{refs[d['id']]}]{kind} {p.get('title') or d['title']} — effective {p.get('effective_date') or '—'} {icons}"):
        if p.get('summary'):
            st.markdown(f"**{md(p.get('summary'))}**")
        c = st.columns(4)
        v = p.get("dates_verified", {})
        c[0].markdown(f"**Issued**  \n{p.get('issue_date') or '—'} {'✓' if v.get('issue_date') else ''}")
        c[1].markdown(f"**Effective**  \n{p.get('effective_date') or '—'} {'✓' if v.get('effective_date') else ''}")
        c[2].markdown(f"**Status**  \n{p.get('status')} · {report.when(p)}")
        c[3].markdown(f"**Relevance**  \n{p.get('relevance')}")
        if p.get("transition_notes"):
            st.markdown(f"**Transition:** {md(p['transition_notes'])}")
        st.markdown(f"**Applies to:** {md(p.get('applies_to') or '—')}  \n**Covers:** {md(p.get('covers') or '—')}"
                    + (f"  \n**Exclusions:** {md(p['exclusions'])}" if p.get("exclusions") else ""))
        if p.get("key_requirements"):
            st.markdown("**Key requirements:**\n" + "\n".join(f"- {md(k)}" for k in p["key_requirements"]))
        if p.get("whats_new"):
            st.markdown(f"**What's new:** {md(p['whats_new'])}")
        if d.get("stats"):
            ok = sum(1 for pt in d["stats"] if pt["verified"])
            st.markdown(f"**Statistics:** {len(d['stats'])} figures extracted, {ok} verified in the document (see Trends).")
        st.markdown(f"**Internal areas affected:** {', '.join(p.get('areas_affected', [])) or '—'}")
        st.markdown(f"Source: [{md(d['title'])}]({d.get('url', '')}) · {'official' if d['tier'] == 1 else 'secondary'} "
                    f"· {d['pages']} pages · profiled by {d['method']}")
        for f in d.get("flags", []):
            st.markdown(f"{SEVERITY_ICON[f['severity']]} **{f['code']}** – {md(f['message'])}")
        if p.get("effective_date_evidence") or p.get("issue_date_evidence"):
            st.caption(f"Date evidence: “{md(p.get('issue_date_evidence'))}” · “{md(p.get('effective_date_evidence'))}”")
        cur = d.get("review") or {}
        with st.form(key=f"rev-{d['id']}"):
            opts = ["accepted", "rejected", "follow-up"]
            dec = st.radio("Decision", opts, horizontal=True, index=opts.index(cur["decision"]) if cur else None)
            note = st.text_input("Note (why?)", value=cur.get("note", ""))
            if st.form_submit_button("Save decision"):
                if not reviewer.strip():
                    st.error("Enter your name in the sidebar first.")
                elif dec is None:
                    st.error("Choose a decision.")
                elif dec != "accepted" and not note.strip():
                    st.error("Please write a short note explaining why.")
                else:
                    pipeline.set_review(rec, d["id"], dec, note, reviewer)
                    st.rerun()
        if cur:
            st.caption(f"Last decision: {cur['decision']} by {cur['reviewer']} at {cur['at']}")


# ===========================================================================
# COMPARE
# ===========================================================================
def render_compare():
    st.subheader("Comparison across jurisdictions")
    st.caption("Each answer cites its document [Ref]. ✓ = supporting quote found in the document.")
    table = report.comparison(rec, rec_pack["questions"])
    # st.table (not st.dataframe) so long answers wrap and can be read in full.
    st.table(pd.DataFrame([{"Question": q, **{j: report.cell_text(table[q].get(j, [])) for j in rec["jurisdictions"]}}
                           for q in rec_pack["questions"]]).set_index("Question"))
    st.caption("“Not stated” = none of the selected documents answers this. Add sources in ① to fill gaps.")
    with st.expander("Evidence behind each answer"):
        for q in rec_pack["questions"]:
            for j, answers in table[q].items():
                for a in answers:
                    st.markdown(f"**{q} — {j} [{a['ref']}]**: {md(a['answer'])}  \n"
                                f"> {md(a.get('evidence') or '(no quote given)')} "
                                f"{'✓' if a.get('evidence_found') else '?'} p.{a.get('page') or '—'}")


# ===========================================================================
# TRENDS
# ===========================================================================
def render_trends():
    points = pipeline.all_points(rec)
    rows = report.trend_rows(rec)
    st.subheader("Trends from official statistics")
    st.caption("Figures are extracted by AI, then **checked by code**: only numbers found in the document are "
               "charted. Changes (▲/▼) are computed by code.")
    if not rows:
        st.info("No statistics with two or more comparable periods yet. In ① tick 📈 statistics documents covering "
                "several periods (e.g. consecutive annual reports), or upload them.")
    else:
        top, seen = [], set()          # the topic's own metrics first, one tile per category
        for r in [r for r in rows if r.get("headline", True) and r.get("current", True)] or rows:
            if r["category"] not in seen and len(top) < 3:
                top.append(r)
                seen.add(r["category"])
        cols = st.columns(len(top))
        for c, t in zip(cols, top):
            c.metric(f"{t['category']} · {t['metric']}", stats.fmt(t["latest"], t["unit"]),
                     f"{stats.arrow(t)[2:]} vs {t['previous_period']}", delta_color="off")
        series = stats.series(points)
        # Headline metrics (cases, amount lost) first in the list; side metrics after.
        headline = {(r["jurisdiction"], r["metric"], r["unit"], r["granularity"]) for r in rows if r.get("headline")}
        # ...and among those, the series with the most categories that have a line opens first.
        lines = lambda k: sum(len(v) >= 2 for v in series[k].values())  # noqa: E731
        options = sorted(series, key=lambda k: (k not in headline, -lines(k), k))
        label = lambda k: f"{k[0]} · {k[1]} ({k[2] or 'count'}, {k[3]})"  # noqa: E731
        key = st.selectbox("Series", options, format_func=label)
        cats = series[key]
        # Default: the biggest categories that have a LINE (2+ periods); a lone dot isn't a trend.
        newest = max(cats[c][-1][0] for c in cats)
        by_latest = sorted(cats, key=lambda c: (len(cats[c]) < 2, cats[c][-1][0] != newest, -cats[c][-1][2]))
        # "Top 10" is a subtotal, not a scam type: available, but not picked by default.
        # "Top 10" and "Others" are leftovers/subtotals, not scam types: available, but not picked by default.
        default = [c for c in by_latest if len(cats[c]) >= 2 and not re.match(r"(top \d+|others?)$", c, re.I)][:5] or by_latest[:5]
        picked = st.multiselect("Categories (max 5)", by_latest, default=default, max_selections=5)
        dark = dark_mode()
        # Big money figures: plot in millions so the axis reads "1,100" not "1,100,000,000".
        biggest = max((v for c in cats for _, _, v, _ in cats[c]), default=0)
        scale, scale_word = (1e9, " (billion)") if biggest >= 5e9 else (1e6, " (million)") if biggest >= 5e6 else (1, "")
        y_title = f"{key[1]}{f' ({key[2]})' if key[2] and key[2] != 'cases' else ''}{scale_word}"
        if picked:
            data = [{"Category": c, "Period": per, "order": i, "Value": val / scale, "Shown": stats.fmt(val, key[2])}
                    for c in picked for i, (_, per, val, _) in enumerate(cats[c])]
            period_order = [per for _, per, _, _ in sorted({pk: (pk, per, 0, 0) for c in picked
                                                             for pk, per, _, _ in cats[c]}.values())]
            colour = alt.Color("Category:N", scale=alt.Scale(domain=picked, range=PALETTE[dark][:len(picked)]),
                               legend=alt.Legend(orient="bottom", title=None))
            base = alt.Chart(pd.DataFrame(data)).encode(
                x=alt.X("Period:N", sort=period_order, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Value:Q", title=y_title), color=colour)
            lines = base.mark_line(strokeWidth=2) + base.mark_point(size=70, filled=True).encode(
                tooltip=["Category", "Period", "Shown"])
            ends = [cats[c][-1][2] / scale for c in picked]
            top_value = max(v / scale for _, _, v, _ in (pt for c in picked for pt in cats[c])) or 1
            # Short label at the line end (full name stays in the legend + tooltip) so it never clips.
            last = pd.DataFrame([{"Category": c if len(c) <= 18 else c[:17] + "…", "Period": cats[c][-1][1], "y": y}
                                 for c, y in zip(picked, spread_labels(ends, top_value * 0.05))])
            labels = alt.Chart(last).mark_text(align="left", dx=8, color=TEXT[dark]).encode(
                x=alt.X("Period:N", sort=period_order), y="y:Q", text="Category:N")  # direct labels, text colour
            st.altair_chart((lines + labels).properties(height=360), width="stretch")

        # What changed: previous vs latest per category (dumbbell, two shades of one hue)
        moved = [r for r in rows if (r["jurisdiction"], r["metric"], r["unit"], r["granularity"]) == key]
        if moved:
            st.markdown("**What changed** (previous → latest period)")
            long = [{"Category": r["category"], "Which": w, "Value": r[f] / scale, "Period": r[f"{f}_period"],
                     "Shown": stats.fmt(r[f], r["unit"])}
                    for r in moved for w, f in (("previous period", "previous"), ("latest period", "latest"))]
            order = [r["category"] for r in sorted(moved, key=lambda r: -(r["pct"] or 0))]
            enc_y = alt.Y("Category:N", sort=order, title=None,
                          axis=alt.Axis(labelOverlap=False, labelLimit=260))  # never drop a row's label
            span = alt.Chart(pd.DataFrame([{"Category": r["category"], "lo": min(r["previous"], r["latest"]) / scale,
                                            "hi": max(r["previous"], r["latest"]) / scale} for r in moved])).mark_rule(
                color="gray", strokeWidth=2).encode(y=enc_y, x="lo:Q", x2="hi:Q")
            dots = alt.Chart(pd.DataFrame(long)).mark_circle(size=110, opacity=1).encode(
                y=enc_y, x=alt.X("Value:Q", title=y_title),
                color=alt.Color("Which:N", scale=alt.Scale(domain=["previous period", "latest period"], range=SHADES[dark]),
                                legend=alt.Legend(orient="bottom", title=None)),
                tooltip=["Category", "Which", "Period", "Shown"])
            tags = alt.Chart(pd.DataFrame([{"Category": r["category"], "x": max(r["previous"], r["latest"]) / scale,
                                            "t": stats.arrow(r)} for r in moved])).mark_text(
                align="left", dx=10, color=TEXT[dark]).encode(
                y=enc_y, x="x:Q", text="t:N")
            st.altair_chart((span + dots + tags).properties(height=60 + 38 * len(moved)), width="stretch")

        st.dataframe(pd.DataFrame([{"Jurisdiction": t["jurisdiction"], "Metric": t["metric"], "Category": t["category"],
                                    "Previous": f"{stats.fmt(t['previous'], t['unit'])} ({t['previous_period']})",
                                    "Latest": f"{stats.fmt(t['latest'], t['unit'])} ({t['latest_period']})",
                                    "Change": stats.arrow(t), "Source": t["ref"]} for t in rows]),
                     hide_index=True, width="stretch")
    revised = stats.revisions(points)
    if revised:
        refs = report.refs(rec)
        with st.expander(f"🔁 {len(revised)} figure(s) revised in a later report - the newer figure is charted"):
            st.caption("⚠️ = the two reports differ by more than 20%. That can be a real revision (e.g. late-reported "
                       "losses) or a figure the AI misread from a table - open both PDFs before relying on it.")
            st.dataframe(pd.DataFrame([{"": "⚠️ check" if v["check"] else "", "Category": v["category"], "Metric": v["metric"], "Period": v["period"],
                                        "Charted (newer)": f"{stats.fmt(v['charted'], v['unit'])} [{refs.get(v['charted_source'])}]",
                                        "Other report": f"{stats.fmt(v['other'], v['unit'])} [{refs.get(v['other_source'])}]"}
                                       for v in revised]), hide_index=True, width="stretch")
    unverified = [p for p in points if not p["verified"]]
    if unverified:
        with st.expander(f"⚠️ {len(unverified)} figure(s) NOT charted - see the reason for each"):
            st.dataframe(pd.DataFrame([{"why not charted": p.get("why_not_charted", "number not found in the document"),
                                        **{k: p.get(k) for k in ("jurisdiction", "metric", "category", "period",
                                                                 "value_as_written", "page", "quote")}}
                                       for p in unverified]),
                         hide_index=True, width="stretch")


# ===========================================================================
# OBLIGATIONS (financial crime leads with this)
# ===========================================================================
def render_obligations():
    st.subheader("Key obligations")
    rows = report.obligations_rows(rec)
    if not rows:
        st.info("No obligations extracted yet.")
    for x in rows:
        with st.container(border=True):
            st.markdown(f"**[{x['Ref']}] {x['Jurisdiction']} – {md(x['Document'])}** · effective {x['Effective']}")
            st.caption(f"Applies to: {md(x['Applies to']) or '—'} · Areas: {x['Areas affected'] or '—'}")
            st.markdown("\n".join(f"- {md(k)}" for k in x["Key obligations"]))


# ===========================================================================
# ASK / REPORT / AUDIT / HOW IT WORKS
# ===========================================================================
def render_ask():
    st.subheader("Ask about a policy")
    refs = report.refs(rec)
    options = {f"[{refs[d['id']]}] {d['profile'].get('title') or d['title']}": d for d in rec["documents"]}
    picked = st.multiselect("Document(s)", list(options), default=list(options)[:1])
    # Statistics briefs don't "apply to" anyone, so they get questions that fit them.
    if picked and all(options[k].get("kind") == "statistics" for k in picked):
        presets = ["What are the headline figures?", "Which categories rose the most?",
                   "Which categories fell?", "What measures are mentioned?"]
    else:
        presets = ["What is this policy about?", "Who does it apply to?", "When does it take effect?",
                   "What are the key obligations for banks?", "What has changed compared with before?"]
    cols = st.columns(len(presets))
    preset = next((p for c, p in zip(cols, presets) if c.button(p, key=f"pre-{p}")), None)
    question = st.text_input("Or ask your own question", value=preset or "")
    if (st.button("Ask", type="primary") or preset) and question and picked:
        docs = [options[k] for k in picked]
        with st.spinner("Reading the document..."):
            answer = ask.ask(question, docs)
        pipeline.log_question(rec, question, [d["id"] for d in docs], answer, reviewer)
        ss.last_answer = (question, answer)
    if ss.last_answer:
        q, a = ss.last_answer
        st.markdown(f"**Q: {md(q)}**")
        if a.get("found_in_document") is False:     # one clear message, not the same thing twice
            st.warning("The selected document(s) don't appear to answer this.")
        else:
            st.markdown(md(a.get("answer", "")))
        for c in a.get("citations", []) or []:
            st.caption(f"{'✓' if c.get('verified') else '?'} {md(c.get('source', ''))} p.{c.get('page')}: “{md(c.get('quote'))}”")


def render_report():
    pending = pipeline.unreviewed_high(rec)
    if rec["status"] == "approved":
        st.success(f"Approved by {rec['approval']['reviewer']} at {rec['approval']['at']}")
    else:
        st.warning("DRAFT – not for reliance until approved.")
        if pending:
            st.error(f"{len(pending)} document(s) with HIGH flags need a decision in Key dates first.")
        ok = st.checkbox("I have reviewed the flagged documents and take responsibility for this report.")
        if st.button("✅ Approve report", disabled=bool(pending) or not ok):
            try:
                pipeline.approve(rec, reviewer)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    text = report.to_markdown(rec, rec_pack)
    c1, c2 = st.columns(2)
    c1.download_button("Download report (Markdown)", text, file_name=f"report-{rec['run_id']}.md")
    c2.download_button("Download audit log (JSON)", json.dumps(rec, indent=2, default=str),
                       file_name=f"run-{rec['run_id']}.json")
    st.caption("Report sections for this topic: " + " → ".join(topics.SECTION_TITLES[s]
                                                                 for s in report.visible_sections(rec, rec_pack)))
    st.divider()
    st.markdown(md(text))


def render_audit():
    st.markdown(f"**Run** `{rec['run_id']}` · **topic** {rec['topic_name']} · **AI** {rec['llm']['provider']} / "
                f"{rec['llm']['model']} · **AI calls** {rec['llm'].get('calls', 0)} · **status** {rec['status']}")
    st.subheader("Discovery agent: every search and preview")
    for disc in rec.get("discovery", []):
        st.markdown(f"**{disc['jurisdiction']}** — {disc['method']} — domains: {', '.join(disc.get('domains', []))}")
        st.dataframe(trace_table(disc["trace"]), hide_index=True, width="stretch")
    st.subheader("Source access log")
    st.dataframe(pd.DataFrame(rec["access_log"]), hide_index=True, width="stretch")
    st.subheader("Reviewer decisions (full history)")
    st.dataframe(pd.DataFrame(rec.get("review_history", [])), hide_index=True, width="stretch")
    st.subheader("Questions asked")
    st.dataframe(pd.DataFrame([{"at": x["at"], "by": x["asked_by"], "question": x["question"],
                                "answer": x["answer"].get("answer", "")[:200]} for x in rec.get("qa_log", [])]),
                 hide_index=True, width="stretch")


def render_how():
    st.markdown(f"""
**Flow:** the discovery agent searches only allowed domains for rules **and** statistics → **you choose** documents →
whole documents read responsibly → AI profiles each one (dates, scope, requirements, areas) and lists figures from
statistics documents → code checks every date and every figure against the document → trends computed by code →
**you review** → approval → a report laid out for this topic.

**Agent guardrails:** allowed domains only · max {config.AGENT_MAX_TURNS} AI turns, {config.AGENT_MAX_SEARCHES} searches,
{config.AGENT_MAX_PREVIEWS} previews per jurisdiction · may only recommend links it actually found · read-only tools ·
every tool call logged.

**Responsible web access:** robots.txt obeyed · honest User-Agent · ≥{config.MIN_SECONDS_BETWEEN_REQUESTS:.0f}s between
requests per site · never bypasses bot checks or logins (use upload instead) · everything cached as evidence.

**This topic's report order:** {" → ".join(topics.SECTION_TITLES[s] for s in pack["report_sections"])}
""")
    st.subheader("Flag rules (edit in checks.py)")
    st.dataframe(pd.DataFrame([{"rule": k, "on": v[0], "severity": v[1], "meaning": v[2]}
                               for k, v in checks.FLAG_RULES.items()]), hide_index=True, width="stretch")


# ===========================================================================
# Build the tabs in this topic's order
# ===========================================================================
VIEWS = {"key_dates": render_key_dates, "comparison": render_compare, "trends": render_trends,
         "trends_if_found": render_trends, "obligations": render_obligations}
if rec:
    topic_views = [s for s in report.visible_sections(rec, rec_pack) if s in VIEWS]
else:
    topic_views = [s for s in pack["report_sections"] if s in VIEWS and s != "trends_if_found"]
extra = [("Ask", render_ask), ("Report & approval", render_report), ("Audit trail", render_audit)]
labels = ["① Find sources"] + [f"{CIRCLED[i]} {topics.SECTION_TITLES[s]}" for i, s in enumerate(topic_views)] \
    + [f"{CIRCLED[len(topic_views) + i]} {name}" for i, (name, _) in enumerate(extra)] + ["ℹ️ How it works"]
tabs = st.tabs(labels)

with tabs[0]:
    render_find_sources()
for tab, view in zip(tabs[1:1 + len(topic_views)], topic_views):
    with tab:
        if rec:
            VIEWS[view]()
        else:
            st.info("Find and profile documents in ① first (or open a previous run).")
for tab, (_, fn) in zip(tabs[1 + len(topic_views):-1], extra):
    with tab:
        if rec and rec["documents"]:
            fn()
        else:
            st.info("No run yet.")
with tabs[-1]:
    render_how()