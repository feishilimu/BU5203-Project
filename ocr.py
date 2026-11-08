"""
ocr.py - read SCANNED PDFs (pictures of pages, no text layer) with Gemini.

WHY
  Some official documents are scans: India's DPDP Act gazette copy, some PCPD guidance.
  The normal PDF reader gets 0 characters from them. Without text the app refuses to
  profile a document (otherwise the AI would "answer" from memory - we saw exactly that
  in a live run). Gemini can read page images, so it transcribes the pages for us.

HOW WE KEEP IT HONEST
  1. The instruction is to TRANSCRIBE, never summarise or complete: unreadable text
     becomes [illegible], and nothing may be added from memory.
  2. Small chunks (a few pages per call), each with page markers. Code checks that the
     number of pages that come back matches the number sent - missing pages are reported.
  3. Every transcription is cached by the file's fingerprint (sha256): you pay once per
     file, and the exact text the AI produced is kept as evidence.
  4. Documents read this way are FLAGGED in the report (checks.py: "read_by_ai_ocr"):
     their "quote found" ticks only prove the quote is in the AI's transcription, so a
     reviewer should compare key quotes and dates with the PDF itself.
  5. It counts against the per-run AI call limit like every other AI call.

Only Gemini is wired up (it accepts PDFs directly). With Bedrock or offline, scanned
PDFs are reported as unreadable, exactly as before.
"""
import hashlib
import io
import json
import re

import config
import llm

PAGES_PER_CALL = 6           # small chunks: fewer dropped pages, easier to check
MAX_OCR_PAGES = 60           # cost guard: longer scans are cut off (and the cut is reported)

_CACHE = config.CACHE_DIR / "ocr"
_CACHE.mkdir(exist_ok=True)

SYSTEM = """You transcribe scanned official documents for bank auditors.
Transcribe the text of EVERY page exactly as printed, in reading order, in the original language
(keep English and other languages as they appear). Keep headings, numbering and table cells
(separate cells with " | "). Rules:
- Do NOT summarise, translate, correct or complete anything. Never add text from memory.
- If a word or line can't be read, write [illegible].
- Start each page with a line "=== PAGE n ===" where n counts from 1 within THIS file.
Output only the transcription."""


def available() -> bool:
    return config.LLM_PROVIDER == "gemini" and bool(config.GEMINI_API_KEY)


def _split(data: bytes, start: int, end: int) -> bytes:
    """Pages [start, end) of a PDF as a new small PDF (so each AI call sees only a few pages)."""
    from pypdf import PdfReader, PdfWriter
    reader, writer = PdfReader(io.BytesIO(data)), PdfWriter()
    for i in range(start, end):
        writer.add_page(reader.pages[i])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _transcribe_chunk(pdf_chunk: bytes) -> tuple[str, str]:
    from google import genai
    from google.genai import types

    llm._count_call()   # per-run kill switch applies here too
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0, max_output_tokens=32000)
    parts = [types.Part.from_bytes(data=pdf_chunk, mime_type="application/pdf"),
             "Transcribe every page of this file."]
    r = client.models.generate_content(model=config.GEMINI_MODEL, contents=parts, config=cfg)
    # WHY a reply can be empty: Gemini may stop with RECITATION (it won't reproduce long published
    # text word for word), SAFETY, or a blocked prompt. We keep the reason so the app can say so.
    reason = ""
    if getattr(r, "prompt_feedback", None) and getattr(r.prompt_feedback, "block_reason", None):
        reason = f"blocked: {r.prompt_feedback.block_reason}"
    elif r.candidates and r.candidates[0].finish_reason:
        reason = str(r.candidates[0].finish_reason).split(".")[-1]
    return (r.text or ""), reason


def _chunk_text(pdf_chunk: bytes) -> tuple[str, str]:
    """Works with the real call (text, reason) and with a simple stand-in that returns text."""
    out = _transcribe_chunk(pdf_chunk)
    return out if isinstance(out, tuple) else (out, "")


def split_pages(text: str, expected: int) -> list[str]:
    """'=== PAGE 1 === ... === PAGE 2 === ...' -> ['...', '...'], padded to the expected count."""
    pieces = re.split(r"^=+\s*PAGE\s+(\d+)\s*=+\s*$", text, flags=re.M | re.I)
    pages: dict[int, str] = {}
    for i in range(1, len(pieces) - 1, 2):
        n = int(pieces[i])
        if 1 <= n <= expected:
            pages[n] = (pages.get(n, "") + "\n" + pieces[i + 1]).strip()
    if not pages and text.strip():       # no markers at all: keep the text on the first page
        pages[1] = text.strip()
    return [pages.get(n, "") for n in range(1, expected + 1)]


def read_scanned_pdf(data: bytes, progress=lambda m: None) -> dict:
    """{'pages': [...], 'pages_missing': [...], 'pages_total': n, 'cut_off': bool, 'model': ...}

    Raises llm.LLMUnavailable when OCR can't run (offline / Bedrock / call limit)."""
    if not available():
        raise llm.LLMUnavailable("Reading scanned PDFs needs Gemini (set GEMINI_API_KEY).")
    key = hashlib.sha256(data).hexdigest()
    cached = _CACHE / f"{key[:32]}.json"
    if cached.exists():
        return json.loads(cached.read_text())

    from pypdf import PdfReader
    total = len(PdfReader(io.BytesIO(data)).pages)
    upto = min(total, MAX_OCR_PAGES)
    pages: list[str] = []
    problems: list[str] = []
    for start in range(0, upto, PAGES_PER_CALL):
        end = min(start + PAGES_PER_CALL, upto)
        progress(f"🔎 AI reading scanned pages {start + 1}-{end} of {total}")
        text, reason = _chunk_text(_split(data, start, end))
        if not text.strip() and end - start > 1:
            # LESSON LEARNED (live run): a 4-page PCPD guide came back completely empty.
            # Retrying one page at a time often gets through; the reason is kept either way.
            problems.append(f"pages {start + 1}-{end}: empty reply ({reason or 'no reason given'}) - retried page by page")
            for one in range(start, end):
                t, why = _chunk_text(_split(data, one, one + 1))
                pages += split_pages(t, 1) if t.strip() else [""]
                if not t.strip():
                    problems.append(f"page {one + 1}: empty reply ({why or 'no reason given'})")
            continue
        if not text.strip():
            problems.append(f"page {start + 1}: empty reply ({reason or 'no reason given'})")
        pages += split_pages(text, end - start)
    result = {
        "pages": pages,
        "pages_total": total,
        "pages_missing": [i + 1 for i, p in enumerate(pages) if not p.strip()],  # checked by code
        "cut_off": total > MAX_OCR_PAGES,
        "model": config.GEMINI_MODEL,
        "problems": problems,      # e.g. "pages 1-4: empty reply (RECITATION)"
    }
    # Only keep a transcription worth keeping: a near-empty one (blocked or failed reply) would
    # otherwise be reused forever. Next run simply tries again.
    if len(" ".join(pages).strip()) >= 800:
        cached.write_text(json.dumps(result))
    return result
