"""
models.py - the shapes of the data passed between steps.

WHY STRUCTURED DATA (instead of letting the AI write free text)?
  - We can CHECK it automatically: does the quote really appear in the source?
  - Every finding has an ID, so a human can accept or reject it individually.
  - It renders cleanly in the app and the report, and is easy to log.
Pydantic validates the AI's output: if the AI returns something malformed,
we find out immediately instead of showing garbage to an auditor.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal[
    "scope",              # which scams / transactions / accounts are covered
    "who_bears_loss",     # how losses are split between bank, telco, customer
    "bank_duty",          # what banks must do
    "other_party_duty",   # telcos, digital platforms, etc.
    "customer_duty",      # what customers are expected to do
    "claims_process",     # reporting, investigation steps, timelines
    "limits",             # caps, excesses, thresholds
    "upcoming_change",    # consultations, proposals, future effective dates
    "statistic",          # numbers about scams and losses
    "other",
]


class RawFinding(BaseModel):
    """What we ask the AI to return for each finding (validated on arrival)."""
    passage_id: str = Field(description="ID of the passage the finding comes from, e.g. S1-P4")
    quote: str = Field(description="Exact words copied from that passage (max ~300 characters)")
    statement: str = Field(description="The finding in plain business English, 1-2 sentences")
    category: Category = "other"
    effective_date: Optional[str] = None
    status: Literal["in force", "upcoming", "proposed", "consultation", "unknown"] = "unknown"
    confidence: Literal["high", "medium", "low"] = "medium"


class Flag(BaseModel):
    code: str
    severity: Literal["high", "medium", "low"]
    message: str


class Review(BaseModel):
    decision: Literal["accepted", "rejected", "follow-up"]
    note: str = ""
    reviewer: str = ""
    at: str = ""


class Finding(RawFinding):
    """A RawFinding plus everything we know about its source, flags and review."""
    id: str
    jurisdiction: str
    section: Literal["A", "B"]
    source_id: str
    source_title: str
    source_url: str
    source_tier: int
    page: Optional[int] = None
    passage_text: str = ""          # kept so reviewers can see the full context
    method: Literal["llm", "offline"] = "llm"
    flags: list[Flag] = []
    review: Optional[Review] = None
