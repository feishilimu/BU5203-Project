"""
report.py - turns a run record into the views banks asked for, and a Markdown report.

SPONSOR FEEDBACK THIS ANSWERS
  "Think about how to present results."  "Dates are important - highlight them,
  maybe in a table."  "Comparison across jurisdictions - the bank has several
  locations."  "No need for paragraphs."

THE VIEWS (used by app.py AND the downloadable report)
  tracker_rows()   KEY DATES TRACKER: one row per document - issue date, effective
                   date, status, countdown, scope, areas affected. Upcoming first.
  comparison()     COMPARISON MATRIX: topic questions x jurisdictions, each cell
                   answered from a specific document (with a reference).
  obligations_rows()  KEY OBLIGATIONS per document (financial crime leads with this)
  trend_rows()     TRENDS from verified statistics: latest vs previous period, ▲/▼
  to_markdown()    the full report, assembled by CODE from reviewed profiles -
                   no new AI text is added at this stage.

EACH TOPIC GETS ITS OWN REPORT
The order of sections comes from the topic pack's "report_sections", e.g.
  scams:            key dates -> trends -> comparison -> profiles
  data protection:  key dates -> comparison -> trends (only if any found) -> profiles
  financial crime:  key dates -> obligations -> trends -> comparison -> profiles
"""
from collections import defaultdict

import dates
import stats
import topics

ABBR = {"Singapore": "SG", "Hong Kong": "HK", "India": "IN", "Indonesia": "ID", "China": "CN",
        "United Kingdom": "UK", "Australia": "AU", "Taiwan": "TW"}


def included(record: dict) -> list[dict]:
    """Documents in the report: not rejected by the reviewer, not judged irrelevant."""
    # "Not relevant" is judged against the RULES topic, so it never excludes a statistics
    # brief (live run: the 2025 brief vanished from the report while its figures were charted).
    return [d for d in record["documents"]
            if not (d.get("review") and d["review"]["decision"] == "rejected")
            and (d["profile"].get("relevance") != "not relevant" or d.get("kind") == "statistics")]


def refs(record: dict) -> dict:
    """Short labels like SG-1, HK-2 for citing documents in tables."""
    counter, out = defaultdict(int), {}
    for d in record["documents"]:
        a = ABBR.get(d["jurisdiction"], d["jurisdiction"][:2].upper())
        counter[a] += 1
        out[d["id"]] = f"{a}-{counter[a]}"
    return out


def when(profile: dict) -> str:
    """Human-readable countdown for the effective date."""
    days = dates.days_until(profile.get("effective_date"))
    if days is None:
        return "Not stated"
    if days > 0:
        return f"⏰ in {days} days" if days <= 365 else f"in {days // 30} months"
    if days == 0:
        return "⏰ today"
    return f"in force ({-days // 365} yr ago)" if days < -365 else f"in force ({-days} days ago)"


def tracker_rows(record: dict) -> list[dict]:
    r = refs(record)
    rows = []
    for d in included(record):
        p = d["profile"]
        verified = p.get("dates_verified", {})
        if d.get("kind") == "statistics":     # no effective date to track: show what it covers
            periods = sorted({(k, pt["period"]) for pt in d.get("stats", []) if pt.get("verified")
                              and (k := stats.period_key(pt["period"]))})
            span = periods[0][1] if periods and periods[0][1] == periods[-1][1] else \
                f"{periods[0][1]} – {periods[-1][1]}" if periods else "statistics"
            covers = f"📈 {span}"
            rows.append({"Ref": r[d["id"]], "Jurisdiction": d["jurisdiction"], "Document": p.get("title") or d["title"],
                         "Type": "statistics", "Issued": (p.get("issue_date") or "—"), "Effective": "n/a",
                         "Status": "n/a", "When": covers, "Applies to": "", "Areas affected": "",
                         "Review": (d.get("review") or {}).get("decision", "not reviewed"), "_days": None, "_id": d["id"]})
            continue
        rows.append({
            "Ref": r[d["id"]],
            "Jurisdiction": d["jurisdiction"],
            "Document": p.get("title") or d["title"],
            "Type": p.get("doc_type", ""),
            "Issued": (p.get("issue_date") or "—") + (" ✓" if verified.get("issue_date") else ""),
            "Effective": (p.get("effective_date") or "—") + (" ✓" if verified.get("effective_date") else ""),
            "Status": p.get("status", "unknown"),
            "When": when(p),
            "Applies to": p.get("applies_to", ""),
            "Areas affected": ", ".join(p.get("areas_affected", [])),
            "Review": (d.get("review") or {}).get("decision", "not reviewed"),
            "_days": dates.days_until(p.get("effective_date")),
            "_id": d["id"],
        })
    # Upcoming (soonest first), then in force (most recent first), then undated.
    def order(row):
        days = row["_days"]
        if days is None:
            return (2, 0)
        return (0, days) if days >= 0 else (1, -days)
    return sorted(rows, key=order)


def comparison(record: dict, questions: list[str]) -> dict:
    """{question: {jurisdiction: [answer dicts]}} from included documents."""
    r = refs(record)
    table = {q: defaultdict(list) for q in questions}
    for d in included(record):
        if d.get("kind") == "statistics":   # statistics describe what happened; they don't set the rules
            continue
        for c in d["profile"].get("comparison", []):
            if c["question"] in table:
                table[c["question"]][d["jurisdiction"]].append(
                    {**c, "ref": r[d["id"]], "doc_title": d["profile"].get("title") or d["title"]})
    return table


def cell_text(answers: list[dict]) -> str:
    """One cell of the comparison. Answers whose supporting quote IS in the document (✓) come
    first; the rest are marked, because the AI may have filled them in from memory.
    (Live run: an outsourcing guideline 'stated' the PDPA breach deadline - no quote found.)"""
    answers = [a for a in answers if (a.get("answer") or "").strip()]   # an empty answer is no answer
    if not answers:
        return "Not stated"
    merged: dict = {}
    for a in sorted(answers, key=lambda a: not a.get("evidence_found")):
        key = " ".join(a["answer"].lower().split())
        m = merged.setdefault(key, {"answer": a["answer"], "refs": [], "ok": False})
        m["refs"].append(a["ref"])
        m["ok"] = m["ok"] or bool(a.get("evidence_found"))
    return " / ".join(f"{m['answer']} [{', '.join(m['refs'])}]" + (" ✓" if m["ok"] else " ⚠️ quote not found")
                      for m in merged.values())


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------
def obligations_rows(record: dict) -> list[dict]:
    r = refs(record)
    return [{"Ref": r[d["id"]], "Jurisdiction": d["jurisdiction"],
             "Document": d["profile"].get("title") or d["title"],
             "Effective": d["profile"].get("effective_date") or "—",
             "Key obligations": d["profile"].get("key_requirements", []),
             "Applies to": d["profile"].get("applies_to", ""),
             "Areas affected": ", ".join(d["profile"].get("areas_affected", []))}
            for d in included(record) if d.get("kind") != "statistics" and d["profile"].get("key_requirements")]


def _points(record: dict) -> list[dict]:
    """Statistics data points from documents the reviewer hasn't rejected."""
    return [pt for d in record["documents"] if not (d.get("review") and d["review"]["decision"] == "rejected")
            for pt in d.get("stats", [])]


def trend_rows(record: dict) -> list[dict]:
    """Trends from VERIFIED data points of non-rejected documents (biggest % change first)."""
    r = refs(record)
    return [{**t, "ref": r.get(t["source_id"], "")} for t in stats.trends(_points(record))]


def _md(text: str) -> str:
    return (text or "").replace("|", "/").replace("\n", " ")


# ---------------------------------------------------------------------------
# Report sections (each returns a list of Markdown lines, without its heading)
# ---------------------------------------------------------------------------
def _sec_key_dates(record: dict, pack: dict) -> list[str]:
    rows = tracker_rows(record)
    soon = [x for x in rows if x["_days"] is not None and x["_days"] >= 0]
    out = ["**Coming into effect**", ""]
    out += [f"- **{x['Effective']}** ({x['When']}) – {x['Jurisdiction']}: {x['Document']} [{x['Ref']}]" for x in soon] \
        or ["_Nothing upcoming in the selected sources._"]
    out += ["", "✓ = date found in the document by an automated check.", "",
            "| Ref | Jurisdiction | Document | Type | Issued | Effective | Status | When | Applies to | Areas affected | Review |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    out += [f"| {x['Ref']} | {x['Jurisdiction']} | {_md(x['Document'])} | {x['Type']} | {x['Issued']} | {x['Effective']} | "
            f"{x['Status']} | {x['When']} | {_md(x['Applies to'])[:120]} | {_md(x['Areas affected'])} | {x['Review']} |"
            for x in rows]
    return out


def _sec_comparison(record: dict, pack: dict) -> list[str]:
    table = comparison(record, pack["questions"])
    js = record["jurisdictions"]
    out = ["Each answer cites its document [Ref]; ✓ = supporting quote found in the document.", "",
           "| Question | " + " | ".join(js) + " |", "|---" * (len(js) + 1) + "|"]
    return out + [f"| {q} | " + " | ".join(_md(cell_text(table[q].get(j, []))) for j in js) + " |"
                  for q in pack["questions"]]


def _sec_trends(record: dict, pack: dict) -> list[str]:
    rows = trend_rows(record)
    if not rows:
        return ["_No statistics with two or more comparable periods were found. Add statistics documents "
                "covering several periods (e.g. annual reports for consecutive years)._"]
    out = ["Computed by code from figures verified in the source documents. Charts are in the app.", "",
           "**Biggest movers**", ""]
    out += [f"- {t['jurisdiction']} · {t['category']} ({t['metric']}): {stats.arrow(t)} "
            f"({t['previous_period']} → {t['latest_period']}) [{t['ref']}]"
            for t in ([r for r in rows if r.get("headline", True) and r.get("current", True)][:5] or rows[:5])]
    out += ["", "| Jurisdiction | Metric | Category | Previous | Latest | Change | Source |", "|---|---|---|---|---|---|---|"]
    out += [f"| {t['jurisdiction']} | {t['metric']} | {_md(t['category'])} | {stats.fmt(t['previous'], t['unit'])} "
            f"({t['previous_period']}) | {stats.fmt(t['latest'], t['unit'])} ({t['latest_period']}) | {stats.arrow(t)} | {t['ref']} |"
            for t in rows]
    r = refs(record)
    revised = stats.revisions(_points(record))
    if revised:
        out += ["", "**Figures revised in a later report** (the newer figure is used above)", ""]
        out += [f"- {'⚠️ **large difference - check the PDFs** · ' if v['check'] else ''}"
                f"{v['jurisdiction']} · {v['category']} ({v['metric']}, {v['period']}): "
                f"{stats.fmt(v['charted'], v['unit'])} [{r.get(v['charted_source'], '')}] vs "
                f"{stats.fmt(v['other'], v['unit'])} [{r.get(v['other_source'], '')}]" for v in revised]
    return out


def _sec_obligations(record: dict, pack: dict) -> list[str]:
    rows = obligations_rows(record)
    if not rows:
        return ["_No obligations extracted._"]
    out = []
    for x in rows:
        out += [f"**[{x['Ref']}] {x['Jurisdiction']} – {_md(x['Document'])}** (effective {x['Effective']})",
                f"*Applies to:* {x['Applies to'] or '—'} · *Areas:* {x['Areas affected'] or '—'}"]
        out += [f"- {k}" for k in x["Key obligations"]] + [""]
    return out


def _sec_profiles(record: dict, pack: dict) -> list[str]:
    docs, r, out = included(record), refs(record), []
    for j in record["jurisdictions"]:
        out += ["", f"### {j}"]
        jd = [d for d in docs if d["jurisdiction"] == j]
        if not jd:
            out.append("_No documents selected._")
        for d in jd:
            p = d["profile"]
            link = f"[{p.get('title') or d['title']}]({d['url']})" if d.get("url") else (p.get("title") or d["title"])
            out += ["", f"**[{r[d['id']]}] {link}**" + ("" if d["tier"] == 1 else " *(secondary source)*")
                    + (" · *statistics*" if d.get("kind") == "statistics" else ""),
                    f"- **Issued:** {p.get('issue_date') or '—'} · **Effective:** {p.get('effective_date') or '—'} "
                    f"· **Status:** {p.get('status')} · {when(p)}"]
            if p.get("transition_notes"):
                out.append(f"- **Transition:** {p['transition_notes']}")
            out += [f"- **Summary:** {p.get('summary') or '—'}",
                    f"- **Applies to:** {p.get('applies_to') or '—'}", f"- **Covers:** {p.get('covers') or '—'}"]
            if p.get("exclusions"):
                out.append(f"- **Exclusions:** {p['exclusions']}")
            if p.get("whats_new"):
                out.append(f"- **What's new:** {p['whats_new']}")
            if p.get("key_requirements"):
                out += ["- **Key requirements:**"] + [f"  - {k}" for k in p["key_requirements"]]
            if d.get("stats"):
                ok = sum(1 for pt in d["stats"] if pt["verified"])
                out.append(f"- **Statistics:** {len(d['stats'])} figures extracted, {ok} verified in the document")
            out.append(f"- **Internal areas affected:** {', '.join(p.get('areas_affected', [])) or '—'}")
            rev = d.get("review")
            flags = " · ".join(f"⚠️ {f['code']}" for f in d.get("flags", []) if f["severity"] != "info")
            out.append(f"- **Review:** {rev['decision'] + ' – ' + rev['note'] if rev else 'not reviewed'}"
                       + (f" · {flags}" if flags else ""))
    return out


SECTIONS = {"key_dates": _sec_key_dates, "comparison": _sec_comparison, "trends": _sec_trends,
            "trends_if_found": _sec_trends, "obligations": _sec_obligations, "profiles": _sec_profiles}


def visible_sections(record: dict, pack: dict) -> list[str]:
    """The topic's sections, in order. 'trends_if_found' is skipped when there are no trends."""
    return [s for s in pack["report_sections"] if not (s == "trends_if_found" and not trend_rows(record))]


def to_markdown(record: dict, pack: dict) -> str:
    r = refs(record)
    out = [f"# External Driver Report – {record['topic_name']}", ""]
    if record["status"] == "approved":
        out.append(f"> ✅ **APPROVED** by {record['approval']['reviewer']} on {record['approval']['at']}")
    else:
        out.append("> ⚠️ **DRAFT – NOT FOR RELIANCE.** AI-assisted research awaiting human review and approval.")
    out += ["", f"Run `{record['run_id']}` · {record['created_at']} · jurisdictions: {', '.join(record['jurisdictions'])} · "
                f"AI: {record['llm']['provider']} ({record['llm']['model']}), {record['llm'].get('calls', 0)} calls"]
    for n, section in enumerate(visible_sections(record, pack), start=1):
        out += ["", f"## {n}. {topics.SECTION_TITLES[section]}", ""] + SECTIONS[section](record, pack)

    docs = included(record)
    excluded = [d for d in record["documents"] if d not in docs]
    out += ["", "## Appendix A – Excluded documents"]
    out += [f"- [{r[d['id']]}] {d['title']} — "
            f"{(d.get('review') or {}).get('note') or d['profile'].get('relevance_reason') or 'excluded'}"
            for d in excluded] or ["_None._"]
    out += ["", "## Appendix B – How sources were found (discovery agent)"]
    for disc in record.get("discovery", []):
        searches = sum(1 for t in disc.get("trace", []) if t.get("tool") == "search_domain")
        previews = sum(1 for t in disc.get("trace", []) if t.get("tool") == "preview_page")
        out.append(f"- **{disc['jurisdiction']}** ({disc['method']}): searched {', '.join(disc.get('domains', []))}; "
                   f"{searches} searches, {previews} previews, {len(disc['recommendations'])} recommended. "
                   f"{disc.get('notes', '')}")
    if not record.get("discovery"):
        out.append("_Sources were chosen from the library / added by hand._")
    out += ["", "## Appendix C – Source access log", "| Source | Status | Tier | Retrieved |", "|---|---|---|---|"]
    out += [f"| [{_md(a['title'])}]({a.get('url') or ''}) | {a['status']}{' – ' + _md(a['reason']) if a.get('reason') else ''} "
            f"| {a.get('tier')} | {a.get('retrieved_at') or ''} |" for a in record["access_log"]]
    out += ["", "## Appendix D – Method",
            "An AI discovery agent searched only allowed official domains (plus labelled statistics sites) and "
            "recommended rules and statistics documents; a human chose which to read. Documents were read in full "
            "(robots.txt respected, rate-limited, cached as evidence). An AI model profiled each document; for "
            "statistics documents it also listed figures, and code kept only figures found in the document. Trends "
            "were computed by code. Every reported date was checked against its document. A human reviewed each "
            "document before approval."]
    return "\n".join(out)
