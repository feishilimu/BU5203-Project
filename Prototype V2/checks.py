"""
checks.py - code-based checks that decide what a human should look at.

WHAT CHANGED FROM v1 (sponsor feedback)
"Not useful to check whether the AI text matches the source text. Check whether
it's RELEVANT; if yes, what's the scope."
So v1's sentence-by-sentence quote flags are gone. v2 checks only what matters
to a bank, and does it silently where possible:

  DATES       the headline facts. Every issue/effective date the AI reports is
              looked for in the document (any format) - not found = HIGH flag,
              because a wrong deadline is the costliest mistake.
  RELEVANCE   documents the AI judges low/not relevant are flagged so the
              reviewer can drop them quickly.
  ALERTS      "effective soon" is a highlight, not a problem (severity "info").
  SAFETY      secondary sources, possible prompt injection, no-AI profiles.
Comparison-table answers get a quiet ✓ when their evidence is found in the
document - visible on hover/expand, but not a flag.

Your team owns FLAG_RULES: switch rules on/off and set severities here.
HIGH flags must be reviewed before a report can be approved.
"""
import re
from difflib import SequenceMatcher

import config
import dates
from models import Flag

FLAG_RULES = {
    # code:                  (enabled, severity, meaning)
    "date_not_in_document":  (True, "high",
                              "A reported date could not be found anywhere in the document - check it before relying on it."),
    "possible_injection":    (True, "high",
                              "The document contains text that looks like instructions aimed at the AI."),
    "not_relevant":          (True, "medium",
                              "The AI judged this document low relevance or not relevant to the topic."),
    "secondary_source":      (True, "medium",
                              "Not an official (Tier 1) regulator or government source."),
    "not_ai_profiled":       (True, "medium",
                              "Profiled without AI (offline) - fields are rough keyword extracts."),
    "read_by_ai_ocr":        (True, "medium",
                              "Scanned PDF: its text was transcribed by AI. Ticks (✓) only show a quote is in that "
                              "transcription - compare key quotes and dates with the PDF itself."),
    "no_effective_date":     (True, "low",
                              "The document doesn't state when it takes effect (or the AI couldn't find it)."),
    "effective_soon":        (True, "info",
                              f"Takes effect within {config.EFFECTIVE_SOON_DAYS} days - plan for it."),
}


# ---------------------------------------------------------------------------
# Evidence matching (kept from v1, now used quietly for comparison answers)
# ---------------------------------------------------------------------------
def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", re.sub(r"[‐-―]", "-", text)).strip()


def _squash(text: str) -> str:
    """Letters and digits only - ignores PDF artifacts like 'real- time'."""
    return re.sub(r"[^a-z0-9]", "", _normalise(text))


def evidence_found(evidence: str, text: str) -> bool:
    """Is this short quote (nearly) present in the document?"""
    q, p = _squash(evidence), _squash(text)
    if len(q) < 8:
        return False
    if q in p:
        return True
    blocks = SequenceMatcher(None, q, p, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks if b.size >= 4) / len(q) >= 0.9


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
def _flag(code: str, extra: str = "") -> Flag | None:
    enabled, severity, message = FLAG_RULES[code]
    return Flag(code=code, severity=severity, message=message + (f" ({extra})" if extra else "")) \
        if enabled else None


def check_document(doc: dict, full_text: str, injection: list[str]) -> dict:
    """Attach flags and evidence ticks to one profiled document (a dict). Returns it."""
    p = doc["profile"]
    flags = []

    for field in ("issue_date", "effective_date"):
        if p.get(field) and not dates.stated_in(p[field], full_text):
            flags.append(_flag("date_not_in_document", f"{field.replace('_', ' ')}: {p[field]}"))
    if injection:
        flags.append(_flag("possible_injection", "; ".join(injection)))
    is_stats = doc.get("kind") == "statistics"   # a statistics brief isn't a rule: no "effective date"
    if p.get("relevance") in ("low", "not relevant") and not is_stats:
        flags.append(_flag("not_relevant", p.get("relevance_reason", "")[:120]))
    if doc.get("tier") != 1:
        flags.append(_flag("secondary_source"))
    if ocr := doc.get("ocr"):
        extra = f"{ocr.get('pages_total')} pages"
        if ocr.get("pages_missing"):
            extra += f"; pages with no text returned: {ocr['pages_missing'][:10]}"
        if ocr.get("cut_off"):
            extra += "; only the first pages were read (length limit)"
        flags.append(_flag("read_by_ai_ocr", extra))
    if doc.get("method") == "offline":
        flags.append(_flag("not_ai_profiled"))
    if not p.get("effective_date") and p.get("relevance") not in ("low", "not relevant") and not is_stats:
        flags.append(_flag("no_effective_date"))
    days = dates.days_until(p.get("effective_date"))
    if days is not None and 0 <= days <= config.EFFECTIVE_SOON_DAYS:
        flags.append(_flag("effective_soon", f"in {days} days"))

    doc["flags"] = [f.model_dump() for f in flags if f]
    # Quiet ticks for the comparison table: is each answer's evidence in the document?
    for c in p.get("comparison", []):
        c["evidence_found"] = bool(c.get("evidence")) and evidence_found(c["evidence"], full_text)
    p["dates_verified"] = {f: bool(p.get(f)) and dates.stated_in(p[f], full_text)
                           for f in ("issue_date", "effective_date")}
    return doc


def has_high_flag(doc: dict) -> bool:
    return any(f["severity"] == "high" for f in doc.get("flags", []))