"""
dates.py - reading and checking dates (the facts banks care about most).

Two jobs:
  parse("16 December 2024")      -> (date(2024, 12, 16), "day")
  stated_in("2024-12-16", text)  -> True if the text really contains that date,
                                    written in ANY common format.

Why so careful? Issue and effective dates are the headline of every profile.
If the AI writes a date that the document doesn't contain, an auditor could
plan around a wrong deadline. So we check every date against the document in
code, and flag any we can't find.
"""
import re
from datetime import date

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_M = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_D = r"(\d{1,2})(?:st|nd|rd|th)?"

# The formats we recognise, most specific first.
_PATTERNS = [
    ("dmy", re.compile(rf"\b{_D}\s+{_M}\s*,?\s+(\d{{4}})\b", re.I)),      # 16 December 2024
    ("mdy", re.compile(rf"\b{_M}\s+{_D},?\s+(\d{{4}})\b", re.I)),         # December 16, 2024
    ("iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")),                   # 2024-12-16
    # Day first, as Singapore, Hong Kong and India write it (live run: SSO prints 31/12/2021).
    ("num", re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")),          # 31/12/2021, 31.12.2021
    ("my",  re.compile(rf"\b{_M}\s+(\d{{4}})\b", re.I)),                   # December 2024
]


def _build(kind: str, g: tuple) -> tuple[date, str] | None:
    try:
        if kind == "dmy":
            return date(int(g[2]), _MONTHS[g[1][:3].lower()], int(g[0])), "day"
        if kind == "mdy":
            return date(int(g[2]), _MONTHS[g[0][:3].lower()], int(g[1])), "day"
        if kind == "iso":
            return date(int(g[0]), int(g[1]), int(g[2])), "day"
        if kind == "num":   # day/month/year (our markets); an impossible month means it isn't one
            return date(int(g[2]), int(g[1]), int(g[0])), "day"
        if kind == "my":
            return date(int(g[1]), _MONTHS[g[0][:3].lower()], 1), "month"
    except (ValueError, KeyError):
        return None
    return None


def parse(text: str | None) -> tuple[date, str] | None:
    """The first date in a string, with its precision ('day', 'month' or 'year')."""
    if not text:
        return None
    for kind, pattern in _PATTERNS:
        m = pattern.search(text)
        if m:
            built = _build(kind, m.groups())
            if built:
                return built
    m = re.search(r"\b(19|20)\d\d\b", text)
    return (date(int(m.group()), 1, 1), "year") if m else None


def all_dates(text: str) -> list[tuple[date, str]]:
    """Every date expression in a text."""
    found = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            built = _build(kind, m.groups())
            if built:
                found.append(built)
    return found


def stated_in(claimed: str, text: str) -> bool:
    """Does the text really contain this date (in any format)?

    Compared at the precision the claim has: a claimed day must match a day in
    the text; a claimed month ("March 2026") must match that month and year.
    """
    parsed = parse(claimed)
    if not parsed:
        return False
    d, precision = parsed
    if precision == "year":
        return str(d.year) in text
    for other, other_precision in all_dates(text):
        if precision == "day" and other_precision == "day" and other == d:
            return True
        if precision == "month" and (other.year, other.month) == (d.year, d.month):
            return True
    return False


def days_until(text: str | None, today: date | None = None) -> int | None:
    parsed = parse(text)
    if not parsed:
        return None
    return (parsed[0] - (today or date.today())).days