"""
tests/check_ai.py - is the AI connected?

Run from the project folder:   python tests/check_ai.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import llm     # noqa: E402

print("Provider:", llm.describe())
if config.LLM_PROVIDER == "offline":
    print("-> Offline. Check .env: GEMINI_API_KEY filled in? File really named '.env' (not '.env.txt')?")
    sys.exit(1)

answer = llm.ask_json("Reply in JSON only.", 'Return exactly this JSON: {"ok": true}')
print("Answer:", answer)
print("✓ AI connected." if answer == {"ok": True} else "Got an answer, but not the expected one - still connected.")