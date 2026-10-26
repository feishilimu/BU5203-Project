"""
check_ocr.py - try Gemini's reading of ONE scanned PDF before using it in a run.

    python tests/check_ocr.py library/IN_digital-personal-data-protection-act-2023_45167c.pdf

Shows whether the PDF has a text layer, then (if it's a scan) what Gemini transcribed:
pages returned, pages missing, and the start of each page. Open the PDF next to it and
spot-check a few lines - that's the human check the "read_by_ai_ocr" flag asks for.
The result is cached, so the real run later won't pay for it again.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config   # noqa: E402
import ocr      # noqa: E402
import scraping  # noqa: E402

if len(sys.argv) < 2:
    sys.exit("Usage: python tests/check_ocr.py path/to/file.pdf")
path = Path(sys.argv[1])
data = path.read_bytes()
text = " ".join(scraping.pdf_to_pages(data)).strip()
print(f"File: {path.name}  |  normal PDF text: {len(text)} characters")
if len(text) >= scraping.MIN_REAL_TEXT_CHARS:
    sys.exit("This PDF already has a text layer - no AI reading needed.")
if not ocr.available():
    sys.exit(f"AI reading needs Gemini: LLM_PROVIDER is '{config.LLM_PROVIDER}'. Set GEMINI_API_KEY in .env.")

result = ocr.read_scanned_pdf(data, progress=print)
print(f"\nPages in PDF: {result['pages_total']}  |  read: {len(result['pages'])}  |  "
      f"missing: {result['pages_missing'] or 'none'}  |  cut off: {result['cut_off']}  |  model: {result['model']}\n")
for i, page in enumerate(result["pages"], start=1):
    print(f"--- page {i}: {' '.join(page.split())[:160]}")