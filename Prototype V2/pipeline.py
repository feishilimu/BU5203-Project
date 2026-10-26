"""
pipeline.py - the ORCHESTRATOR: runs the steps and keeps the audit record.

THE v2 FLOW
    ① discovery.py   agent searches allowed domains, recommends documents
        |             HUMAN ticks which to read  (+ library uploads, pasted links)
    ② sources.py     fetch each chosen document responsibly
    ③ profiler.py    AI turns each document into a profile (dates, scope, ...)
       stats.py       + for statistics documents: figures -> verified data points
    ④ checks.py      code checks dates & relevance -> flags / highlights
    ⑤ app.py         tracker table, comparison matrix, Q&A, report
                      HUMAN reviews each document, then approves

WHY THE OVERALL ORDER IS FIXED
The agent is free INSIDE discovery (it chooses searches and recommendations),
but the steps around it are fixed, so every run is comparable and auditable.
Humans decide at both gates: what gets read, and what gets approved.

THE RUN RECORD (runs/<id>.json) IS THE AUDIT TRAIL
inputs . AI model . agent tool calls . sources read/blocked . profiles . flags .
every human decision . every Q&A . the approval.
"""
import json
from datetime import datetime, timezone

import checks
import config
import llm
import profiler
import reading
import sources
import stats
import topics


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_record(topic_id: str, jurisdictions: list[str]) -> dict:
    return {
        "run_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "created_at": _now(),
        "topic": topic_id,
        "topic_name": topics.get(topic_id)["name"],
        "jurisdictions": jurisdictions,
        "llm": {"provider": config.LLM_PROVIDER, "model": llm.model_name(), "calls": 0},
        "status": "draft",
        "approval": None,
        "discovery": [],       # what the agent searched, previewed and recommended
        "access_log": [],      # every document: read, cached, blocked... and why
        "documents": [],       # one profile per document
        "notes": [],
        "review_history": [],
        "qa_log": [],
    }


def profile_sources(record: dict, chosen: list[dict], progress=print) -> dict:
    """Steps ②-④ for the sources a human chose. Fills and saves the record."""
    pack = topics.get(record["topic"])
    # LESSON LEARNED (live run): a recommended link AND its uploaded copy were both ticked,
    # so four documents were read twice and every comparison answer appeared twice.
    # One document per link (or per file); the first choice wins.
    # Prefer a copy we already HAVE (library / manual download) over trying the website again.
    has_copy = lambda s: bool(s.get("local_file") or sources.find_manual_copy(s.get("url", "")))  # noqa: E731
    unique, seen = [], set()
    for src in sorted(chosen, key=lambda s: not has_copy(s)):
        keys = {k for k in (src.get("url"), src.get("local_file")) if k}
        if keys & seen:
            continue
        seen |= keys
        unique.append(src)
    chosen = unique
    if len(chosen) > config.MAX_DOCUMENTS_PER_RUN:
        record["notes"].append({"note": f"Only the first {config.MAX_DOCUMENTS_PER_RUN} sources were read (limit)."})
    for i, src in enumerate(chosen[: config.MAX_DOCUMENTS_PER_RUN], start=1):
        progress(f"📄 Reading {i}/{len(chosen)}: {src['title'][:70]}")
        doc = sources.get_document({**src, "_progress": progress})   # progress: shows AI reading scanned pages
        log = {k: doc.get(k) for k in ("id", "title", "url", "jurisdiction", "origin", "status", "reason",
                                        "tier", "retrieved_at", "sha256", "kind", "local_file", "manual_copy")}
        if doc.get("ocr"):
            log["ocr"] = {k: doc["ocr"][k] for k in ("pages_total", "pages_missing", "cut_off", "model")}
        if doc.get("status") in sources.FAILED_STATUSES:     # a human will need to download this one
            log["suggested_file"] = sources.suggested_filename(doc)
        record["access_log"].append(log)
        if not doc.get("pages"):
            continue
        doc["key"] = f"S{len(record['documents']) + 1}"   # unique even when files are added to a run later
        progress(f"🧠 Profiling: {src['title'][:70]}")
        prof, passages, method = profiler.profile(doc, pack, record["notes"])
        entry = {
            "id": doc["id"], "jurisdiction": doc["jurisdiction"], "title": doc["title"],
            "url": doc.get("url", ""), "tier": doc["tier"], "origin": doc.get("origin", ""),
            "local_file": doc.get("local_file"),   # so Q&A can re-open the same saved copy
            "official": doc.get("official", False),
            "ocr": doc.get("ocr"),                  # set when a scanned PDF was transcribed by AI
            "method": method, "profile": prof.model_dump(),
            "passages_used": [{"id": p["id"], "page": p["page"], "score": p.get("score", 0)} for p in passages],
            "pages": len(doc["pages"]), "review": None,
        }
        # Rule or statistics? Decided BEFORE the checks, because the checks differ.
        entry["kind"] = "statistics" if (src.get("kind") == "statistics"
                                         or prof.doc_type == "statistics") else "rule"
        if entry["kind"] == "statistics":
            # LESSON LEARNED (live run): a police brief "answered" which scams the
            # liability rules cover. Statistics describe what happened; they don't set rules.
            entry["profile"].update(doc_type="statistics", status="unknown", comparison=[])
        full_text = " ".join(doc["pages"])
        injection = reading.injection_signals(full_text)
        checks.check_document(entry, full_text, injection)
        # Statistics documents get an extra step: figures -> verified data points (for trends).
        if entry["kind"] == "statistics":
            progress(f"📈 Extracting statistics: {src['title'][:60]}")
            entry["stats"] = stats.extract(doc, pack, record["notes"])
        record["documents"] = [d for d in record["documents"] if d["id"] != entry["id"]] + [entry]
    record["llm"]["calls"] = llm.calls_made
    save(record)
    progress("✅ Done.")
    return record


# ---------------------------------------------------------------------------
# Human-in-the-loop
# ---------------------------------------------------------------------------
def manual_downloads_needed(record: dict) -> list[dict]:
    """Sources that couldn't be read automatically and still have no document in this run."""
    have = {d.get("url") for d in record["documents"] if d.get("url")}
    out, seen = [], set()
    for a in reversed(record["access_log"]):           # the LATEST attempt for each link decides
        url = a.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        already = any(sources.same_document(a, d) for d in record["documents"])   # read via another link
        if a.get("status") in sources.FAILED_STATUSES and url not in have and not already:
            out.append({**a, "suggested_file": a.get("suggested_file") or sources.suggested_filename(a)})
    return out[::-1]


def all_points(record: dict) -> list[dict]:
    """Every statistics data point from documents the reviewer hasn't rejected."""
    return [pt for d in record["documents"] if not (d.get("review") and d["review"]["decision"] == "rejected")
            for pt in d.get("stats", [])]


def set_review(record: dict, doc_id: str, decision: str, note: str, reviewer: str) -> None:
    review = {"decision": decision, "note": note, "reviewer": reviewer, "at": _now()}
    for d in record["documents"]:
        if d["id"] == doc_id:
            d["review"] = review
    record["review_history"].append({"document": doc_id, **review})  # every decision kept
    save(record)


def unreviewed_high(record: dict) -> list[dict]:
    return [d for d in record["documents"] if checks.has_high_flag(d) and not d.get("review")]


def approve(record: dict, reviewer: str) -> None:
    if not reviewer.strip():
        raise ValueError("Enter the reviewer's name before approving.")
    pending = unreviewed_high(record)
    if pending:
        raise ValueError(f"{len(pending)} document(s) with HIGH flags still need a decision.")
    record["status"] = "approved"
    record["approval"] = {"reviewer": reviewer, "at": _now()}
    save(record)


def log_question(record: dict, question: str, doc_ids: list[str], answer: dict, asked_by: str) -> None:
    record["qa_log"].append({"at": _now(), "asked_by": asked_by, "documents": doc_ids,
                             "question": question, "answer": answer})
    save(record)


# ---------------------------------------------------------------------------
# Saving / loading (the audit trail)
# ---------------------------------------------------------------------------
def save(record: dict) -> None:
    (config.RUNS_DIR / f"{record['run_id']}.json").write_text(json.dumps(record, indent=2, default=str))


def list_runs() -> list[str]:
    return sorted((p.stem for p in config.RUNS_DIR.glob("*.json")), reverse=True)


def load(run_id: str) -> dict:
    return json.loads((config.RUNS_DIR / f"{run_id}.json").read_text())