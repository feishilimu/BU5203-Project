"""
tests/check_agent.py - watch the discovery agent work LIVE (needs internet + AI key).

Run from the project folder:
    python tests/check_agent.py                                  (data protection, Singapore)
    python tests/check_agent.py financial_crime "Hong Kong"      (any topic / jurisdiction)

It prints every search and preview the agent decides to make, then its
recommendations. Uses a few AI calls; answers are NOT cached for the agent.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discovery  # noqa: E402
import llm        # noqa: E402

topic = sys.argv[1] if len(sys.argv) > 1 else "data_protection"
jurisdiction = sys.argv[2] if len(sys.argv) > 2 else "Singapore"
print(f"AI: {llm.describe()} | topic: {topic} | jurisdiction: {jurisdiction}\n")

result = discovery.discover(topic, jurisdiction, progress=print)
print(f"\nMethod: {result['method']}  |  AI calls: {llm.calls_made}  |  notes: {result.get('notes')}")
print(f"Domains allowed: {', '.join(result.get('domains', []))}\n")
for r in result["recommendations"]:
    flag = "  ⚠️ site blocks bots: download by hand" if r.get("needs_manual_download") else ""
    icon = "📈" if r.get("kind") == "statistics" else "📜"   # statistics feed the Trends tab
    print(f"[{r['relevance']:>6}] {icon} {r['title']}\n         {r['url']}\n         why: {r.get('why')}{flag}\n")
if not result["recommendations"]:
    print("No recommendations. If it says 'rate limit', wait a minute and retry.")
