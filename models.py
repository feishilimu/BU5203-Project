"""
models.py - the shape of a REGULATORY PROFILE (what we extract from each document).

SPONSOR FEEDBACK THIS ANSWERS
  "Date is important - issue date, effective date - highlight and present in a table."
  "What is the scope?"  "Is it relevant? If yes, what's the scope, map to internal."
  "No point asking 'are you compliant' - the bank already must follow it."
  "No need for paragraphs."
So instead of v1's paragraph "findings", each document becomes ONE profile with
fixed fields. Fixed fields can go straight into tables, be sorted by date, be
compared across countries, and be checked by code.

Pydantic validates what the AI returns. The "before" validators below tidy up
small variations (e.g. "In Force" -> "in force") instead of throwing the whole
profile away.
"""
from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

STATUSES = ["in force", "upcoming", "consultation", "proposed", "superseded", "unknown"]
DOC_TYPES = ["act", "regulation", "guideline", "notice", "consultation", "statement",
             "statistics", "other"]
RELEVANCE = ["high", "medium", "low", "not relevant"]


def _as_text(v) -> str:
    """AI quirks -> plain text: None -> "", a list -> "a; b", a number -> "5"."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "; ".join(_as_text(x) for x in v if x is not None)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_as_text(x)}" for k, x in v.items())
    return str(v)


def _as_page(v):
    """'5', 5, 'p. 5', '5-6' -> 5 ; anything else -> None (a page is a nice-to-have)."""
    import re
    m = re.search(r"\d+", str(v)) if v is not None else None
    return int(m.group()) if m else None


def _pick(value, allowed: list[str], default: str) -> str:
    v = str(value or "").strip().lower()
    return next((a for a in allowed if v == a or v.startswith(a)), default)


class ComparisonAnswer(BaseModel):
    question: str          # one of the topic pack's questions
    answer: str            # short answer in plain English
    evidence: str = ""     # short exact quote supporting it
    page: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def _tidy(cls, data):
        if not isinstance(data, dict):
            return {"question": "", "answer": _as_text(data)}
        return {"question": _as_text(data.get("question")), "answer": _as_text(data.get("answer")),
                "evidence": _as_text(data.get("evidence")), "page": _as_page(data.get("page"))}


class Profile(BaseModel):
    """What the AI must return for each document."""
    relevance: str = "medium"
    relevance_reason: str = ""
    title: str = ""
    issuer: str = ""
    doc_type: str = "other"
    issue_date: Optional[str] = None
    issue_date_evidence: str = ""
    effective_date: Optional[str] = None
    effective_date_evidence: str = ""
    transition_notes: str = ""       # phase-ins, grace periods, different dates for parts
    status: str = "unknown"
    applies_to: str = ""             # scope: WHO must comply
    covers: str = ""                 # scope: WHAT activities / data / products
    exclusions: str = ""             # scope: what is NOT covered
    key_requirements: list[str] = []
    whats_new: str = ""
    areas_affected: list[str] = []   # mapped to the topic pack's internal areas
    comparison: list[ComparisonAnswer] = []
    summary: str = ""                # two sentences, for the "what is this policy about" view

    # LESSON LEARNED (first live run): the AI sometimes returns null, a list or a number
    # where we expect text. Strict checking threw away the WHOLE profile for one odd
    # field. Now we tidy the shape first; only the content rules below stay strict.
    @model_validator(mode="before")
    @classmethod
    def _tidy_shape(cls, data):
        if not isinstance(data, dict):
            return data
        data = {k: v for k, v in data.items() if k in cls.model_fields}   # ignore extra keys
        for name, field in cls.model_fields.items():
            if name not in data:
                continue
            if field.annotation is str:
                data[name] = _as_text(data[name])
            elif name == "comparison":
                v = data[name]
                data[name] = [x for x in (v if isinstance(v, list) else [v] if v else []) if x]
        return data

    @field_validator("relevance", mode="before")
    @classmethod
    def _relevance(cls, v):
        return _pick(v, RELEVANCE, "medium")

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, v):
        return _pick(v, STATUSES, "unknown")

    @field_validator("doc_type", mode="before")
    @classmethod
    def _doc_type(cls, v):
        return _pick(v, DOC_TYPES, "other")

    @field_validator("key_requirements", "areas_affected", mode="before")
    @classmethod
    def _list(cls, v):
        if isinstance(v, str):
            return [v] if v.strip() else []
        return [str(x) for x in (v or []) if str(x).strip()][:8]

    @field_validator("issue_date", "effective_date", mode="before")
    @classmethod
    def _date(cls, v):
        v = (str(v).strip() if v is not None else "")
        return None if v.lower() in ("", "null", "none", "n/a", "not stated", "unknown") else v


class Flag(BaseModel):
    code: str
    severity: Literal["high", "medium", "low", "info"]
    message: str
