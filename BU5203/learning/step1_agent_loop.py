"""
STEP 1 - Your first agent: an LLM + tools + a loop.

THE ONE IDEA TO TAKE AWAY
An "agent" is not magic. It is this loop:

    1. Send the task (and the list of tools) to the LLM.
    2. The LLM replies EITHER with a final answer
                     OR with "please run tool X with inputs Y".
    3. If it asked for a tool: we run it, send the result back, go to 1.
    4. If it gave a final answer: stop.

The LLM decides WHAT to do next (that's the "agentic" part).
Our code decides WHETHER it's allowed and actually DOES it (that's the control).

HOW THIS RELATES TO THE APP
The app (app.py + pipeline.py) uses a FIXED pipeline: predictable and auditable.
This file is the next step up: an agent that decides for itself which official
sources to search and read. It uses the same gateway (sources.py), so it gets
the same whitelist, robots.txt and rate limits - it can't go anywhere else.

Needs Amazon Bedrock (tool use via the Converse API), so it runs once your AWS
account is active and BEDROCK_MODEL is set in .env.

Run from the project folder:  python learning/step1_agent_loop.py
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # find the project's modules

import boto3  # noqa: E402

import config  # noqa: E402
import sources  # noqa: E402


def today() -> str:
    return date.today().isoformat()


# ---- The tools: each is a Python function + a description the AI reads ------
def web_search(query: str, jurisdiction: str = "") -> list[dict]:
    return sources.discover(query, jurisdiction or None, official_only=True)


def read_page(url: str) -> dict:
    doc = sources.get_document({"id": "agent", "jurisdiction": "?", "title": url, "url": url})
    text = "\n".join(doc.get("pages", []))
    return {"url": url, "status": doc.get("status"), "reason": doc.get("reason"),
            "text": f"<untrusted_document>{text[:12000]}</untrusted_document>"}


TOOL_FUNCTIONS = {"web_search": web_search, "read_page": read_page}
TOOL_CONFIG = {"tools": [
    {"toolSpec": {"name": "web_search",
                  "description": "Search ONLY official regulator/government sites. Returns titles, URLs, snippets.",
                  "inputSchema": {"json": {"type": "object", "properties": {
                      "query": {"type": "string"},
                      "jurisdiction": {"type": "string", "enum": config.JURISDICTIONS}},
                      "required": ["query"]}}}},
    {"toolSpec": {"name": "read_page",
                  "description": "Read the full text of a page found with web_search (to confirm dates, caps, duties).",
                  "inputSchema": {"json": {"type": "object", "properties": {"url": {"type": "string"}},
                                           "required": ["url"]}}}},
]}

llm = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)


def run_agent(task: str, system_prompt: str, max_turns: int = 10) -> tuple[str, list[dict]]:
    """Run one agent until it answers or hits max_turns.

    Returns (final_answer, trace).
    The TRACE is a log of every tool call - this becomes our audit trail
    later ("which agent did what, with which source?").
    """
    # 'messages' is the conversation memory. The LLM has no memory of its
    # own between API calls - we resend the whole history every time.
    # In Converse, every message's content is a LIST of blocks.
    messages = [{"role": "user", "content": [{"text": task}]}]
    trace = []

    for turn in range(1, max_turns + 1):
        # --- 1. Ask the LLM what to do next --------------------------------
        response = llm.converse(
            modelId=config.BEDROCK_MODEL,
            system=[{"text": system_prompt}],      # the agent's "job description"
            messages=messages,
            toolConfig=TOOL_CONFIG,                # the menu of tools it may request
            inferenceConfig={"maxTokens": 4096, "temperature": 0.2},  # low = more factual
        )
        reply = response["output"]["message"]

        # Always store the reply in the history, including any tool
        # requests - the model needs to see them next turn.
        messages.append(reply)

        # --- 2. Did it finish? --------------------------------------------
        # stopReason == "tool_use" means "I want a tool". "end_turn" means done.
        if response["stopReason"] != "tool_use":
            final_text = "".join(b.get("text", "") for b in reply["content"])
            return final_text, trace

        # --- 3. Run every tool it asked for -------------------------------
        tool_results = []
        for block in reply["content"]:
            if "toolUse" not in block:
                continue  # skip any "thinking out loud" text blocks
            request = block["toolUse"]   # {"toolUseId", "name", "input"}
            name, args = request["name"], request["input"]

            print(f"[turn {turn}] agent calls {name}({args})")
            started = time.time()

            # SAFETY: only run tools that are in our whitelist. The LLM can
            # *ask* for anything; it can only *get* what we allow.
            func = TOOL_FUNCTIONS.get(name)
            try:
                if func is None:
                    raise ValueError(f"Unknown tool: {name}")
                result = func(**args)
                status = "success"
            except Exception as e:
                # Return errors to the LLM instead of crashing - it can often
                # recover (e.g. try a different query).
                result, status = {"error": str(e)}, "error"

            trace.append({
                "turn": turn,
                "tool": name,
                "input": args,
                "status": status,
                "seconds": round(time.time() - started, 2),
                # Record which URLs came back - useful for the audit trail.
                "urls": [r.get("url") for r in result] if isinstance(result, list)
                        else [result.get("url")] if isinstance(result, dict) else [],
            })

            # Each result must quote the toolUseId it answers.
            tool_results.append({
                "toolResult": {
                    "toolUseId": request["toolUseId"],
                    "content": [{"text": json.dumps(result)}],
                    "status": status,
                }
            })

        # Tool results go back as a "user" message - that's how the API
        # represents "here's what happened when your tool ran".
        messages.append({"role": "user", "content": tool_results})

    # --- 4. Safety net -----------------------------------------------------
    # Without max_turns, a confused agent could loop forever and burn money.
    # This is a mini "kill switch" - another control to mention in the report.
    return "STOPPED: agent hit max_turns without finishing.", trace


# ---------------------------------------------------------------------------
# Try it out
# ---------------------------------------------------------------------------
RESEARCHER_PROMPT = f"""You are a regulatory research analyst supporting a bank's
internal audit team. Today's date is {today()}.

Rules:
- Use the tools to find information. Do not rely on memory for facts,
  dates or figures.
- Every factual point must end with the URL that supports it, in brackets.
- If you cannot find a source for something, say "Not found" - never guess.
- Prefer official regulator sources over news.
- Note the date of each development and whether it is in force or upcoming.
"""

if __name__ == "__main__":
    print(f"Using Bedrock model {config.BEDROCK_MODEL} in {config.AWS_REGION}")
    task = (
        "Search Singapore sources. In Singapore, who bears the loss when a bank "
        "customer falls victim to a phishing scam? Summarise the key duties on "
        "banks and telcos, the effective date, and what happens if a duty is breached."
    )
    answer, trace = run_agent(task, RESEARCHER_PROMPT)

    print("\n================ ANSWER ================\n")
    print(answer)
    print("\n================ TRACE (audit trail) ================\n")
    print(json.dumps(trace, indent=2))
