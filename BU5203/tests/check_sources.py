"""
tests/check_sources.py - can we read each curated source? (needs internet, no AI)

Run from the project folder:   python tests/check_sources.py

For every document in source_registry.py it prints whether it was read, and if
not, why (robots.txt, unreachable, refused...). Use it to:
  - check internet/firewall before a demo
  - spot sources that need a manual download into the library
It's polite: it obeys robots.txt and waits between requests, so it takes a minute.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reading          # noqa: E402
import source_registry  # noqa: E402
import sources          # noqa: E402

ICON = {"ok": "✅", "cached": "✅", "library": "📁", "blocked_by_robots": "🚫",
        "unreachable": "📡", "refused": "⛔", "not_official": "❓", "error": "⚠️",
        "bot_check": "🤖", "too_little_text": "📄"}

print(f"{'':2} {'status':18} {'pages':>5} {'chars':>7} {'relevant':>8}  source")
for src in source_registry.REGISTRY:
    doc = sources.get_document(src)
    pages = doc.get("pages", [])
    chars = sum(len(p) for p in pages)
    kept = reading.select_passages(reading.split_passages(pages, "S1")) if pages else []
    print(f"{ICON.get(doc['status'], '?'):2} {doc['status']:18} {len(pages):>5} {chars:>7} {len(kept):>8}  "
          f"{src['id']}")
    if doc.get("reason"):
        print(f"{'':24}↳ {doc['reason']}")

print("\n✅ read   📁 library   🚫 robots.txt says no   📡 unreachable   ⛔ refused (403)   "
      "🤖 bot-check page   📄 too little text   ⚠️ error")
print("Anything not ✅/📁: download it in your browser and add it via the app's 'Add a document by hand'.")