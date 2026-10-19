"""
pipeline.py - the ORCHESTRATOR: runs every step in a fixed order and logs it.

THE FLOW (each step is a separate, testable file)
    sources.py    get each selected document  (registry / library / web)
        |
    reading.py    split into passages, keep the most relevant ones
        |
    extractor.py  AI agent turns passages into structured findings
        |
    checks.py     code-based checks attach flags (quote? numbers? official?)
        |
    app.py        a HUMAN reviews flagged findings, then approves the report

WHY A FIXED ORDER (and not an AI "manager" deciding what to do next)?
Banks need predictable, auditable processes: every run follows the same steps
and produces a comparable log. The AI is autonomous only inside its own step.

THE RUN RECORD
Everything about a run (inputs, which sources were read or blocked, which AI
model, every finding with its flags, every human decision) is saved as one JSON
file in runs/. That file IS the audit trail: "which agent, which version, whose
approval?"
"""
import json
from datetime import datetime, timezone

import checks
import config
import extractor
import llm
import reading
import sources as gateway
from models import Finding


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(selected_sources: list[dict], jurisdictions: list[str], progress=print) -> dict:
    """Run the whole pipeline on the sources a human selected. Returns the run record."""
    llm.calls_made = 0
    record = {
        "run_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "created_at": _now(),
        "topic": config.TOPIC,
        "jurisdictions": jurisdictions,
        "llm": {"provider": config.LLM_PROVIDER, "model": llm.model_name()},
        "status": "draft",
        "approval": None,
        "access_log": [],   # one entry per source: read, cached, blocked...
        "documents": [],    # what we read and which passages we kept
        "notes": [],        # anything unusual, e.g. "AI unavailable, used offline mode"
        "findings": [],
    }

    # ---- Step 1 + 2: get documents and pick relevant passages -----------------
    docs = []
    if len(selected_sources) > config.MAX_DOCUMENTS_PER_RUN:
        record["notes"].append({"step": "collect",
                                "note": f"Only the first {config.MAX_DOCUMENTS_PER_RUN} sources were read (limit)."})
    for i, src in enumerate(selected_sources[: config.MAX_DOCUMENTS_PER_RUN], start=1):
        progress(f"Reading {i}/{len(selected_sources)}: {src['title'][:70]}")
        doc = gateway.get_document(src)
        record["access_log"].append({
            k: doc.get(k) for k in ("id", "title", "url", "jurisdiction", "origin", "status",
                                    "reason", "tier", "retrieved_at", "sha256")
        })
        if not doc.get("pages"):
            continue
        doc["key"] = f"S{i}"
        passages = reading.split_passages(doc["pages"], doc["key"])
        doc["selected"] = reading.select_passages(passages)
        doc["header"] = reading.header_passage(doc["pages"], doc["key"])  # dates & status context
        docs.append(doc)
        record["documents"].append({
            "id": doc["id"], "key": doc["key"], "title": doc["title"],
            "passages_total": len(passages),
            "passages_kept": [{"id": p["id"], "page": p["page"], "score": p["score"]} for p in doc["selected"]],
        })

    # ---- Step 3: extraction agent, one call per country ------------------------
    findings: list[Finding] = []
    for jurisdiction in jurisdictions:
        country_docs = [d for d in docs if d["jurisdiction"] == jurisdiction and d["selected"]]
        if not country_docs:
            record["notes"].append({"step": "extract", "jurisdiction": jurisdiction,
                                    "note": "No readable sources - nothing to analyse."})
            continue
        progress(f"Extracting findings for {jurisdiction} with {llm.describe()}...")
        if config.LLM_PROVIDER in ("gemini", "bedrock"):
            findings += extractor.extract_with_llm(jurisdiction, country_docs, record["notes"])
        else:
            findings += extractor.extract_offline(country_docs)

    # ---- Step 4: code-based checks -> flags ------------------------------------
    progress("Checking findings against their sources...")
    published = {d["id"]: d.get("published") for d in docs}
    headers = {d["id"]: (d["header"] or {}).get("text", "") for d in docs}
    injection = {p["id"]: reading.injection_signals(p["text"])
                 for d in docs for p in d["selected"] + ([d["header"]] if d["header"] else [])}
    for f in findings:
        checks.check(f, published=published.get(f.source_id), injection=injection.get(f.passage_id),
                     header=headers.get(f.source_id, ""))

    record["findings"] = [f.model_dump() for f in findings]
    record["llm"]["calls"] = llm.calls_made
    record["coverage"] = coverage(record)
    save(record)
    progress("Done.")
    return record


# ---------------------------------------------------------------------------
# Coverage: did we actually research every country? (brief: "completeness")
# ---------------------------------------------------------------------------
def coverage(record: dict) -> dict:
    out = {}
    for j in record["jurisdictions"]:
        log = [a for a in record["access_log"] if a["jurisdiction"] == j]
        fs = [f for f in record["findings"] if f["jurisdiction"] == j]
        out[j] = {
            "sources_selected": len(log),
            "sources_read": sum(a["status"] in ("ok", "cached", "library") for a in log),
            "sources_blocked_or_failed": [a["title"] for a in log if a["status"] not in ("ok", "cached", "library")],
            "findings": len(fs),
            "categories_covered": sorted({f["category"] for f in fs}),
        }
    return out


# ---------------------------------------------------------------------------
# Human-in-the-loop: reviews and approval
# ---------------------------------------------------------------------------
def set_review(record: dict, finding_id: str, decision: str, note: str, reviewer: str) -> None:
    review = {"decision": decision, "note": note, "reviewer": reviewer, "at": _now()}
    for f in record["findings"]:
        if f["id"] == finding_id:
            f["review"] = review
    # Keep EVERY decision, even if someone changes their mind later (audit trail).
    record.setdefault("review_history", []).append({"finding_id": finding_id, **review})
    save(record)


def unreviewed_high_flags(record: dict) -> list[dict]:
    """Findings with a HIGH flag that no human has looked at yet."""
    return [f for f in record["findings"]
            if any(fl["severity"] == "high" for fl in f["flags"]) and not f.get("review")]


def approve(record: dict, reviewer: str) -> None:
    """Approve the report. Refused while any HIGH-flag finding is unreviewed."""
    if not reviewer.strip():
        raise ValueError("Enter the reviewer's name before approving.")
    pending = unreviewed_high_flags(record)
    if pending:
        raise ValueError(f"{len(pending)} high-severity finding(s) still need a decision.")
    record["status"] = "approved"
    record["approval"] = {"reviewer": reviewer, "at": _now()}
    save(record)


# ---------------------------------------------------------------------------
# Saving and loading runs (the audit trail)
# ---------------------------------------------------------------------------
def save(record: dict) -> None:
    (config.RUNS_DIR / f"{record['run_id']}.json").write_text(json.dumps(record, indent=2))


def list_runs() -> list[str]:
    return sorted((p.stem for p in config.RUNS_DIR.glob("*.json")), reverse=True)


def load(run_id: str) -> dict:
    return json.loads((config.RUNS_DIR / f"{run_id}.json").read_text())