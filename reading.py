"""
reading.py - turns a long document into a few relevant, citable passages.

(v2: keywords now come from the topic pack, and passages that state dates get a
boost, because issue and effective dates are what banks look for first.)

WHY THIS STEP EXISTS
A regulation can be 50+ pages. Sending all of it to the AI is slow and costly,
but cutting it off after the first few pages is worse: in the SRF guidelines the
"who bears the loss" rules only start on page 8! So instead we:
  1. split the WHOLE document into passages of a few sentences,
  2. score each passage for relevance to our topic (keyword weights in config),
  3. keep the top few, and give each an ID like "S1-P7" (source 1, passage 7).
The AI must cite those IDs, so every finding traces back to an exact passage
and page. That traceability is what the brief means by "source-grounded".

This step uses no AI at all - it's plain, explainable Python.
"""
import re

import config

# Sentence boundary: a full stop/semicolon/colon followed by space and a capital,
# digit, bracket or quote. Imperfect, but simple and good enough for chunking.
_SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z0-9(\"“‘])")


def tidy_pdf_text(text: str) -> str:
    """Undo common PDF extraction artifacts so passages read naturally.

    'real- time' -> 'real-time',  'high -risk' -> 'high-risk',  'device ,' -> 'device,'
    (Footnote numbers glued into sentences can't be fixed safely, so we leave them;
    checks.py tolerates them when matching quotes.)
    """
    text = re.sub(r"(\w)- (\w)", r"\1-\2", text)
    text = re.sub(r"(\w) -(\w)", r"\1-\2", text)
    return re.sub(r" ([,;:.)])", r"\1", text)


def split_passages(pages: list[str], source_key: str) -> list[dict]:
    """Cut every page into passages of roughly config.PASSAGE_TARGET_CHARS."""
    passages = []
    for page_no, page_text in enumerate(pages, start=1):
        text = re.sub(r"\s+", " ", page_text).strip()   # collapse PDF line breaks
        text = tidy_pdf_text(text)
        if not text:
            continue
        # Add sentences to the current passage until it reaches the target size.
        current = ""
        for sentence in _SENTENCE_END.split(text):
            if current and len(current) + len(sentence) > config.PASSAGE_TARGET_CHARS:
                passages.append({"text": current, "page": page_no})
                current = ""
            current = f"{current} {sentence}".strip()
        if current:
            passages.append({"text": current, "page": page_no})  # page kept for citations
    for i, p in enumerate(passages, start=1):
        p["id"] = f"{source_key}-P{i}"
    return passages


# Words that usually sit next to the dates banks care about.
DATE_WORDS = ["effective", "commence", "come into force", "comes into force", "come into operation",
              "comes into operation", "with effect from", "issue date", "issued on", "date of issue",
              "takes effect", "take effect", "in force", "transition", "grace period"]
_MONTH_YEAR = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{4}\b"
                         r"|\b\d{1,2} (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{4}\b"
                         r"|\b\d{4}-\d{2}-\d{2}\b", re.I)


def relevance(text: str, keywords: dict) -> int:
    """Score = sum of (keyword weight x times it appears), plus a bonus for dates.

    keywords comes from the topic pack, e.g. {3: ["personal data", ...], 2: [...], 1: [...]}.
    """
    lower = text.lower()
    score = sum(weight * lower.count(word) for weight, words in keywords.items() for word in words)
    # Dates are the headline output for banks, so passages stating them get a boost
    # even if they don't mention the topic words (e.g. "These Regulations come into
    # operation on 1 March 2026").
    if _MONTH_YEAR.search(text) and any(w in lower for w in DATE_WORDS):
        score += 6
    return score


def select_passages(passages: list[dict], keywords: dict,
                    k: int = config.TOP_PASSAGES_PER_DOCUMENT) -> list[dict]:
    """Keep the k most relevant passages, then put them back in document order."""
    for order, p in enumerate(passages):
        p["score"] = relevance(p["text"], keywords)
        p["order"] = order
    best = sorted((p for p in passages if p["score"] > 0), key=lambda p: -p["score"])[:k]
    return sorted(best, key=lambda p: p["order"])


def find_dates(text: str, limit: int = 8) -> list[str]:
    """Date-looking strings in a text (used to show the agent and the reviewer)."""
    return list(dict.fromkeys(m.group(0) for m in _MONTH_YEAR.finditer(text)))[:limit]


# ---------------------------------------------------------------------------
# Prompt-injection detection (idea adapted from our groupmate's version)
# ---------------------------------------------------------------------------
# A web page could contain text aimed at the AI, e.g. "ignore previous
# instructions". We look for such phrases so the passage can be flagged, and we
# always wrap source text in <passage> tags marked as untrusted data.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) instructions",
    r"disregard (all |any )?(previous|prior|above)",
    r"you are now",
    r"new instructions",
    r"system prompt",
    # Narrow on purpose: laws say "act as a data intermediary" - that's not an attack.
    r"act as (an?|the) (ai|assistant|chatbot|language model|different)",
    r"output only",
    r"</?passage",
]


def injection_signals(text: str) -> list[str]:
    lower = text.lower()
    return [p for p in INJECTION_PATTERNS if re.search(p, lower)]


HEADER_CHARS = 1200


def header_passage(pages: list[str], source_key: str) -> dict | None:
    """The start of the document: title, issue date, effective date, status.

    Relevance ranking often skips the first page (it rarely mentions "loss" or
    "liability"), yet that's where documents state WHEN they apply. So we always
    give the AI the document's opening text as context, labelled as the header.
    """
    for page_no, page_text in enumerate(pages, start=1):
        text = tidy_pdf_text(re.sub(r"\s+", " ", " ".join(pages[page_no - 1:])).strip())
        if text:
            return {"id": f"{source_key}-H", "page": page_no, "text": text[:HEADER_CHARS],
                    "role": "document header", "score": 0, "order": -1}
    return None


def as_untrusted_block(passage: dict) -> str:
    """Wrap a passage so the AI can tell data apart from instructions."""
    clean = re.sub(r"</?passage[^>]*>", "", passage["text"], flags=re.I)  # no fake tags
    role = f' role="{passage["role"]}"' if passage.get("role") else ""
    return f'<passage id="{passage["id"]}" page="{passage["page"]}"{role}>\n{clean}\n</passage>'
