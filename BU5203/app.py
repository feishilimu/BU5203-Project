"""
app.py - the screen the auditor uses (Streamlit).

Run:  streamlit run app.py      (opens http://localhost:8501)

HOW STREAMLIT WORKS (the one thing to know)
Streamlit re-runs this whole script from top to bottom every time the user
clicks something. Anything that must survive between clicks is kept in
st.session_state (a dictionary that persists for the browser session).

THE FOUR STEPS ON SCREEN = THE HUMAN-IN-THE-LOOP DESIGN
  1 Sources   the human chooses WHAT the agent may read (registry, uploads,
              and search results only once ticked)
  2 Review    the agent's findings, with flags; the human accepts/rejects
  3 Report    approval is blocked until every HIGH-flag finding is reviewed
  4 Audit     everything that happened, for "which agent, whose approval?"
"""
import json

import pandas as pd
import streamlit as st

import checks
import config
import llm
import pipeline
import report
import sources

st.set_page_config(page_title="Liability Radar", page_icon="🛰️", layout="wide")
ss = st.session_state
ss.setdefault("discovered", [])   # search results the user may tick
ss.setdefault("record", None)     # the current run


def md(text: str) -> str:
    """Escape '$' so amounts like S$50,000 aren't rendered as maths by Streamlit."""
    return (text or "").replace("$", "\\$")


SEVERITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡"}

# ===========================================================================
# Sidebar: settings that apply to every step
# ===========================================================================
with st.sidebar:
    st.title("AIF Liability Radar")
    st.caption("External driver research for internal audit · scam & fraud liability")
    st.markdown(f"**AI model:** {llm.describe()}")
    if config.LLM_PROVIDER == "offline":
        st.info("No AI key found, so findings will be raw excerpts. Add GEMINI_API_KEY "
                "(or Bedrock settings) to .env and restart to enable AI extraction.")
    jurisdictions = st.multiselect("Jurisdictions", config.JURISDICTIONS, default=config.JURISDICTIONS)
    reviewer = st.text_input("Your name (reviewer)", help="Recorded with every decision and the approval.")

    runs = pipeline.list_runs()
    if runs:
        chosen = st.selectbox("Open a previous run", ["—"] + runs)
        if chosen != "—" and st.button("Open run"):
            ss.record = pipeline.load(chosen)
            st.rerun()

tab_sources, tab_review, tab_report, tab_audit, tab_help = st.tabs(
    ["① Sources", "② Review findings", "③ Report & approval", "④ Audit trail", "How it works"])

# ===========================================================================
# 1. SOURCES
# ===========================================================================
with tab_sources:
    if ss.get("flash"):
        st.info(ss.pop("flash"))
    st.subheader("Choose what the agent may read")
    st.write("Curated official documents are ticked by default. Uploaded documents and search "
             "results are only read if you tick them: **you decide the sources, not the AI.**")

    candidates = (sources.registry_sources(jurisdictions) + sources.library_sources(jurisdictions)
                  + [d for d in ss.discovered if d["jurisdiction"] in jurisdictions])
    table = pd.DataFrame([{
        "include": c["origin"] != "discovery",
        "jurisdiction": c["jurisdiction"],
        "title": c["title"],
        "origin": c["origin"],
        "section": c.get("section", "A"),
        "url": c.get("url", ""),
        "why": c.get("why", ""),
    } for c in candidates])

    if table.empty:
        st.warning("Select at least one jurisdiction in the sidebar.")
        edited = table
    else:
        edited = st.data_editor(
            table, hide_index=True, width="stretch",
            disabled=["jurisdiction", "title", "origin", "section", "url", "why"],
            column_config={
                "include": st.column_config.CheckboxColumn("Read?"),
                "url": st.column_config.LinkColumn("Link"),
                "section": st.column_config.TextColumn("Sec.", help="A = regulatory, B = industry"),
            })

    col1, col2 = st.columns(2)
    with col1, st.expander("➕ Add a document by hand (library)"):
        st.caption("For documents the scraper can't reach, or that aren't public "
                   "(in real use: the bank's own compensation policy).")
        up = st.file_uploader("PDF, HTML or text file", type=["pdf", "html", "htm", "txt"])
        up_j = st.selectbox("Jurisdiction", config.JURISDICTIONS, key="up_j")
        up_title = st.text_input("Title", key="up_title")
        up_url = st.text_input("Original web address (if any)", key="up_url")
        up_official = st.checkbox("This is an official regulator/government document", key="up_off")
        up_section = st.radio("Section", ["A", "B"], horizontal=True, key="up_sec",
                              captions=["Regulatory", "Industry"])
        if st.button("Add to library", disabled=up is None):
            sources.add_to_library(up.name, up.getvalue(), up_j, up_title, up_url,
                                   up_official, up_section, reviewer)
            st.success("Added. It now appears in the table above.")
            st.rerun()

    with col2, st.expander("🔎 Discover new official documents (search)"):
        st.caption("Searches ONLY Tier 1 official domains. Results are added unticked - "
                   "review them before including.")
        d_j = st.selectbox("Jurisdiction", jurisdictions or config.JURISDICTIONS, key="d_j")
        d_q = st.text_input("Search", value=sources.suggested_queries(d_j)[0], key="d_q")
        if st.button("Search official sites"):
            with st.spinner("Searching..."):
                found = sources.discover(d_q, d_j)
            known = {d["url"] for d in ss.discovered} | {c.get("url") for c in candidates}
            new = [f for f in found if f["url"] not in known]
            ss.discovered += new
            # Messages vanish on rerun, so park it in session_state and show it at the top.
            ss.flash = (f"{len(new)} new candidate(s) added to the table, unticked - review them first."
                        if new else "Nothing new found (or the search engine is rate-limiting - try later).")
            st.rerun()

    selected = [c for c, row in zip(candidates, edited.to_dict("records")) if row["include"]] \
        if not edited.empty else []
    st.divider()
    if st.button(f"▶ Run analysis on {len(selected)} source(s)", type="primary", disabled=not selected):
        with st.status("Running the agent pipeline...", expanded=True) as status:
            ss.record = pipeline.run(selected, jurisdictions, progress=st.write)
            status.update(label="Finished - go to ② Review findings", state="complete")

# ===========================================================================
# 2. REVIEW
# ===========================================================================
with tab_review:
    rec = ss.record
    if not rec:
        st.info("Run an analysis in ① Sources (or open a previous run from the sidebar).")
    else:
        fs = rec["findings"]
        high = [f for f in fs if any(fl["severity"] == "high" for fl in f["flags"])]
        c = st.columns(4)
        c[0].metric("Findings", len(fs))
        c[1].metric("With flags", sum(1 for f in fs if f["flags"]))
        c[2].metric("Reviewed", sum(1 for f in fs if f.get("review")))
        c[3].metric("High flags not yet reviewed", len(pipeline.unreviewed_high_flags(rec)))
        for note in rec.get("notes", []):
            st.caption(f"ℹ️ {note.get('jurisdiction', '')} {note['note']}")

        f1, f2 = st.columns([2, 3])
        show_j = f1.multiselect("Jurisdiction", rec["jurisdictions"], default=rec["jurisdictions"])
        show = f2.radio("Show", ["Needs review first", "High flags only", "All"], horizontal=True)
        order = {"high": 0, "medium": 1, "low": 2, None: 3}
        view = [f for f in fs if f["jurisdiction"] in show_j]
        if show == "High flags only":
            view = [f for f in view if f in high]
        if show == "Needs review first":
            view.sort(key=lambda f: (bool(f.get("review")), order[min(
                (fl["severity"] for fl in f["flags"]), key=order.get, default=None)]))

        for f in view:
            with st.container(border=True):
                st.markdown(f"**{md(f['statement'])}**")
                when = f"effective {f['effective_date']}" if f.get("effective_date") else f["status"]
                st.caption(f"{f['id']} · {f['jurisdiction']} · Section {f['section']} · "
                           f"{report.CATEGORY_LABELS.get(f['category'], f['category'])} · {when} · "
                           f"AI confidence: {f['confidence']} · method: {f['method']}")
                page = f", p.{f['page']}" if f.get("page") else ""
                tier = "official (Tier 1)" if f["source_tier"] == 1 else "secondary (Tier 2)"
                st.markdown(f"Source: [{md(f['source_title'])}]({f['source_url']}){page} — {tier}")
                for fl in f["flags"]:
                    st.markdown(f"{SEVERITY_ICON[fl['severity']]} **{fl['code']}** – {md(fl['message'])}")
                with st.expander("Evidence: quote and full passage"):
                    st.markdown(f"> {md(f['quote'])}")
                    st.caption("Full passage the AI was given:")
                    st.write(md(f["passage_text"]))

                current = f.get("review") or {}
                with st.form(key=f"form-{f['id']}"):
                    options = ["accepted", "rejected", "follow-up"]
                    decision = st.radio("Decision", options, horizontal=True,
                                        index=options.index(current["decision"]) if current else None)
                    note = st.text_input("Note (why?)", value=current.get("note", ""))
                    if st.form_submit_button("Save decision"):
                        if not reviewer.strip():
                            st.error("Enter your name in the sidebar first.")
                        elif decision is None:
                            st.error("Choose a decision.")
                        elif decision != "accepted" and not note.strip():
                            # An audit trail needs the reason behind every rejection/follow-up.
                            st.error("Please write a short note explaining why.")
                        else:
                            pipeline.set_review(rec, f["id"], decision, note, reviewer)
                            st.toast(f"Saved: {f['id']} {decision}")
                            st.rerun()
                if current:
                    st.caption(f"Last decision: {current['decision']} by {current['reviewer']} at {current['at']}")

# ===========================================================================
# 3. REPORT & APPROVAL
# ===========================================================================
with tab_report:
    rec = ss.record
    if not rec:
        st.info("No run yet.")
    else:
        pending = pipeline.unreviewed_high_flags(rec)
        if rec["status"] == "approved":
            st.success(f"Approved by {rec['approval']['reviewer']} at {rec['approval']['at']}")
        else:
            st.warning("DRAFT – not for reliance until approved.")
            if pending:
                st.error(f"{len(pending)} finding(s) with HIGH flags still need a decision in ② Review.")
            confirm = st.checkbox("I have reviewed the flagged findings and take responsibility for this report.")
            if st.button("✅ Approve report", disabled=bool(pending) or not confirm):
                try:
                    pipeline.approve(rec, reviewer)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        text = report.to_markdown(rec)
        d1, d2 = st.columns(2)
        d1.download_button("Download report (Markdown)", text, file_name=f"report-{rec['run_id']}.md")
        d2.download_button("Download full audit log (JSON)", json.dumps(rec, indent=2),
                           file_name=f"run-{rec['run_id']}.json")
        st.divider()
        st.markdown(md(text))

# ===========================================================================
# 4. AUDIT TRAIL
# ===========================================================================
with tab_audit:
    rec = ss.record
    if not rec:
        st.info("No run yet.")
    else:
        st.markdown(f"**Run** `{rec['run_id']}` · **AI** {rec['llm']['provider']} / {rec['llm']['model']} "
                    f"· **AI calls** {rec['llm'].get('calls', 0)} · **status** {rec['status']}")
        st.subheader("Source access log")
        st.caption("Every source: read, served from cache, or blocked (e.g. by robots.txt) - and why.")
        st.dataframe(pd.DataFrame(rec["access_log"]), hide_index=True, width="stretch")
        st.subheader("Passages selected per document")
        st.json(rec["documents"], expanded=False)
        st.subheader("Coverage")
        st.json(rec.get("coverage", {}), expanded=False)
        st.subheader("Reviewer decisions (full history)")
        st.dataframe(pd.DataFrame(rec.get("review_history", [])), hide_index=True, width="stretch")

# ===========================================================================
# 5. HOW IT WORKS (transparency for users and judges)
# ===========================================================================
with tab_help:
    st.markdown("""
**Pipeline:** Sources (human-chosen) → read whole documents → rank passages → AI extracts findings
that must quote a passage → code checks every quote and number → human reviews flags → approval.

**Responsible web access:** robots.txt obeyed · honest User-Agent · ≥3 s between requests per site ·
no logins or paywalls · everything cached as evidence. See `docs/responsible_scraping.md`.
""")
    st.subheader("Flag rules (edit in checks.py)")
    st.dataframe(pd.DataFrame([{"rule": k, "on": v[0], "severity": v[1], "meaning": v[2]}
                               for k, v in checks.FLAG_RULES.items()]),
                 hide_index=True, width="stretch")