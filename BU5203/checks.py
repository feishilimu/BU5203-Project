"""
checks.py - flags findings a human should look at carefully.

KEY IDEA: CHECKS IN CODE, NOT JUST "ASK THE AI IF IT'S RIGHT"
Asking an AI to grade its own work is weak: it tends to agree with itself.
(Our groupmate's first version marked every claim "verified, 100%" - including
shallow ones.) So most checks here are plain Python that can be tested:
  - is the quote really in the source passage?
  - does every number in the statement appear in the source?
  - is the source official?
Only one check ("ai_unsure") uses the AI's own opinion, and it can only ADD
a flag, never remove one.

FLAG_RULES below is the single place to switch rules on/off and set their
severity. Add new rules by writing a function and registering it. Severity
drives the human-in-the-loop step: the report can't be approved until a human
has reviewed every finding with a HIGH flag.
"""
import re
from datetime import date
from difflib import SequenceMatcher

from models import Finding, Flag

FLAG_RULES = {
    # code:                (enabled, severity, what it means)
    "quote_not_in_source": (True, "high",
                            "The quoted text could not be found in the cited passage - possible fabrication."),
    "quote_approximate":   (True, "low",
                            "The quote is close to, but not exactly, the source text (check wording)."),
    "number_not_in_source": (True, "high",
                             "The statement contains a number or date that does not appear in the source passage."),
    "date_not_in_source":  (True, "high",
                            "The effective date isn't written in the passage or the document header - possibly inferred or invented."),
    "unknown_passage":     (True, "high",
                            "The AI cited a passage ID that doesn't exist."),
    "secondary_source":    (True, "medium",
                            "Source is not an official (Tier 1) regulator or government site."),
    "possible_injection":  (True, "high",
                            "The source passage contains text that looks like instructions aimed at the AI."),
    "ai_unsure":           (True, "medium",
                            "The AI itself rated its confidence as low."),
    "no_date_for_rule":    (False, "low",
                            "Regulatory finding without an effective date - check when it applies."),
    "not_summarised":      (True, "medium",
                            "Produced without AI (offline excerpt) - needs a human to interpret."),
    "stale_source":        (True, "low",
                            "Source was published more than 3 years ago - check it's still current."),
}


def _normalise(text: str) -> str:
    """Lower-case, unify quotes/dashes and collapse spaces, so formatting differences don't count."""
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―]", "-", text)
    return re.sub(r"\s+", " ", text).strip()


def _squash(text: str) -> str:
    """Keep only letters and digits. PDF text often has artifacts like 'real- time',
    'high -risk' or 'device ,' - comparing letters/digits only makes those irrelevant."""
    return re.sub(r"[^a-z0-9]", "", _normalise(text))


def quote_match(quote: str, passage: str) -> str:
    """'exact', 'approximate' or 'missing'.

    exact       - every letter/digit of the quote appears, in order, in the passage
    approximate - at least 90% of it does, in chunks of 4+ characters (e.g. the PDF
                  has a footnote number '8' stuck in the middle: 'material su m 8 to')
    missing     - otherwise: treat as possibly invented
    """
    q, p = _squash(quote), _squash(passage)
    if not q:
        return "missing"
    if q in p:
        return "exact"
    # Count quote characters found in the passage in matching runs of 4+ characters.
    # Requiring runs (not single letters) stops an invented sentence from "matching"
    # just because its letters appear scattered around a long passage.
    blocks = SequenceMatcher(None, q, p, autojunk=False).get_matching_blocks()
    matched = sum(b.size for b in blocks if b.size >= 4)
    return "approximate" if matched / len(q) >= 0.9 else "missing"


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_missing(statement: str, passage: str) -> list[str]:
    """Numbers in the statement (amounts, %, days, years) that the passage doesn't contain."""
    in_source = {n.replace(",", "") for n in _NUMBER.findall(passage)}
    return [n for n in _NUMBER.findall(statement) if n.replace(",", "") not in in_source]


_MONTHS = "january february march april may june july august september october november december".split()


def date_supported(date_text: str, source: str) -> bool:
    """Is this date actually written in the source?

    Tolerant of format: '2024-12-16', '16 Dec 2024' and '16 December 2024' all count
    if the source says '16 December 2024'. We check the year, and the day number if
    the date has one. Missing year or day in the source -> not supported.
    """
    years = re.findall(r"(?:19|20)\d\d", date_text)
    source_numbers = {n.lstrip("0") for n in re.findall(r"\d+", source)}
    if not years or not all(y in source_numbers for y in years):
        return False
    rest = re.sub(r"(?:19|20)\d\d", " ", date_text)
    numbers = [n.lstrip("0") for n in re.findall(r"\d+", rest)]
    month_name = next((m for m in _MONTHS if m[:3] in rest.lower()), None)
    if month_name:  # "16 December 2024": the day is the remaining number
        days = numbers
    elif len(numbers) == 2:  # ISO "2024-12-16": month then day
        days = numbers[1:]
    else:
        days = numbers
    return all(d in source_numbers for d in days)


def _flag(code: str, extra: str = "") -> Flag | None:
    enabled, severity, message = FLAG_RULES[code]
    if not enabled:
        return None
    return Flag(code=code, severity=severity, message=message + (f" ({extra})" if extra else ""))


def check(finding: Finding, published: str | None = None, injection: list[str] | None = None,
          header: str = "") -> Finding:
    """Run every rule on one finding and attach the flags.

    header = the document's opening text (title, dates). Numbers and dates may come
    from there too, because the AI is allowed to use it for dates and status.
    """
    flags = []
    passage = finding.passage_text
    evidence = f"{passage} {header}"

    if not passage:
        flags.append(_flag("unknown_passage", finding.passage_id))
    else:
        match = quote_match(finding.quote, passage)
        if match == "missing":
            flags.append(_flag("quote_not_in_source"))
        elif match == "approximate":
            flags.append(_flag("quote_approximate"))
        missing = numbers_missing(finding.statement, evidence)
        if missing:
            flags.append(_flag("number_not_in_source", ", ".join(missing)))
        if finding.effective_date and not date_supported(finding.effective_date, evidence):
            flags.append(_flag("date_not_in_source", finding.effective_date))

    if finding.source_tier != 1:
        flags.append(_flag("secondary_source"))
    if injection:
        flags.append(_flag("possible_injection", "; ".join(injection)))
    if finding.method == "offline":
        flags.append(_flag("not_summarised"))
    elif finding.confidence == "low":
        flags.append(_flag("ai_unsure"))
    year = re.search(r"(19|20)\d\d", published or "")
    if year and date.today().year - int(year.group()) > 3:
        flags.append(_flag("stale_source", published))

    finding.flags = [f for f in flags if f]
    return finding


def worst_severity(finding: Finding) -> str | None:
    order = {"high": 0, "medium": 1, "low": 2}
    return min((f.severity for f in finding.flags), key=order.get, default=None)