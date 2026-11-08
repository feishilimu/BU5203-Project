"""
llm.py - one doorway to whichever AI model we use (Gemini, Bedrock or none).

TWO WAYS WE TALK TO THE AI
  ask_json(system, prompt)
      One question -> one JSON answer. Used for document profiles and Q&A.

  run_tool_agent(system, task, tools, functions, ...)
      The AGENT LOOP. The AI is given tools (e.g. "search a domain") and decides
      for itself which to call, in what order, and when to stop:
          1. send the task + tool menu to the AI
          2. AI answers with a final text, OR asks us to run a tool
          3. we run the tool (only if it's on the menu), send the result back
          4. repeat until it's done or hits max_turns (the kill switch)
      Our code decides WHETHER a tool may run; the AI decides WHICH and WHEN.

GOVERNANCE NOTES
  - cache: the same prompt is never paid for twice; re-runs are free.
  - calls_made + MAX_LLM_CALLS_PER_RUN: a hard stop on spending.
  - Gemini's FREE tier may use prompts to improve Google's products, so only
    public documents are ever sent. Production would use Bedrock / a paid tier.
"""
import hashlib
import json
import re

import config

_CACHE = config.CACHE_DIR / "llm"
_CACHE.mkdir(exist_ok=True)

calls_made = 0  # AI calls in the current run (the pipeline resets this)


class LLMUnavailable(Exception):
    """Offline mode, or the per-run call limit was reached."""


def describe() -> str:
    if config.LLM_PROVIDER == "gemini":
        return f"Google Gemini ({config.GEMINI_MODEL})"
    if config.LLM_PROVIDER == "bedrock":
        return f"Amazon Bedrock ({config.BEDROCK_MODEL})"
    return "Offline (no AI - keyword methods only)"


def model_name() -> str:
    return {"gemini": config.GEMINI_MODEL, "bedrock": config.BEDROCK_MODEL}.get(config.LLM_PROVIDER, "none")


def _count_call() -> None:
    global calls_made
    if config.LLM_PROVIDER not in ("gemini", "bedrock"):
        raise LLMUnavailable("Offline mode: no AI model configured.")
    if calls_made >= config.MAX_LLM_CALLS_PER_RUN:
        raise LLMUnavailable(f"Run limit of {config.MAX_LLM_CALLS_PER_RUN} AI calls reached (kill switch).")
    calls_made += 1


def parse_json(text: str):
    """Models sometimes wrap JSON in ```fences``` or add a sentence. Be forgiving."""
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if match:
            return json.loads(match.group(1))
        raise


# ===========================================================================
# 1. One question -> one JSON answer
# ===========================================================================
def generate(client, **kwargs):
    """client.models.generate_content with a short retry for TEMPORARY failures.

    LESSON LEARNED (live run): "ServerError" = Google's servers were busy (HTTP 5xx), and
    429 = rate limit (common on the free tier). Both usually clear within seconds, so we
    wait and try again (2s, then 6s) instead of losing that step. Real errors - a wrong
    model name (404), a bad key - are not retried: they fail at once with their message."""
    import time
    from google.genai import errors
    for wait in (2, 6, None):
        try:
            return client.models.generate_content(**kwargs)
        except errors.APIError as e:
            temporary = isinstance(e, errors.ServerError) or getattr(e, "code", None) == 429
            if not temporary or wait is None:
                raise
            time.sleep(wait)


def _gemini_text(system: str, prompt: str, json_mode: bool) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(system_instruction=system, temperature=0.1,
                                      response_mime_type="application/json" if json_mode else None)
    return generate(client, model=config.GEMINI_MODEL, contents=prompt, config=cfg).text or ""


def _bedrock_text(system: str, prompt: str) -> str:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
    r = client.converse(modelId=config.BEDROCK_MODEL, system=[{"text": system}],
                        messages=[{"role": "user", "content": [{"text": prompt}]}],
                        inferenceConfig={"maxTokens": 4096, "temperature": 0.1})
    return "".join(b.get("text", "") for b in r["output"]["message"]["content"])


def ask_json(system: str, prompt: str):
    """Send one prompt, get parsed JSON back. Cached on disk by prompt."""
    key = hashlib.sha256(f"{config.LLM_PROVIDER}|{model_name()}|{system}|{prompt}".encode()).hexdigest()
    cached = _CACHE / f"{key[:32]}.json"
    if cached.exists():
        return json.loads(cached.read_text())["answer"]
    # LESSON LEARNED (live run): now and then the model returns broken JSON (a missing
    # comma, a cut-off reply). One retry with a reminder almost always fixes it, which is
    # much better than falling back to the rough offline profile.
    for attempt in (1, 2):
        _count_call()
        ask = prompt if attempt == 1 else (prompt + "\n\nIMPORTANT: your previous reply was not valid JSON. "
                                                     "Reply with ONE valid JSON object only. Keep text fields short.")
        text = (_gemini_text(system, ask, json_mode=True) if config.LLM_PROVIDER == "gemini"
                else _bedrock_text(system, ask))
        try:
            answer = parse_json(text)
            break
        except json.JSONDecodeError:
            if attempt == 2:
                raise
    cached.write_text(json.dumps({"answer": answer}))   # only GOOD answers are cached
    return answer


# ===========================================================================
# 2. The agent loop (tool calling)
# ===========================================================================
# Tools are described once, in a neutral format:
#   {"name": "search_domain", "description": "...", "parameters": {JSON schema}}
# and translated below into each provider's own format.

def _run_tool(name: str, args: dict, functions: dict, trace: list, turn: int) -> dict:
    """Run one tool the AI asked for - ONLY if it's on our menu - and log it."""
    func = functions.get(name)
    try:
        if func is None:
            raise ValueError(f"Tool '{name}' is not allowed.")
        result = func(**args)
        status = "ok"
    except Exception as e:  # errors go back to the AI, which can often recover
        result, status = {"error": str(e)}, "error"
    trace.append({"turn": turn, "tool": name, "input": args, "status": status,
                  "result_summary": _summarise(result)})
    return result if isinstance(result, dict) else {"result": result}


def _summarise(result) -> str:
    """Short version of a tool result for the audit log (not the whole page text)."""
    if isinstance(result, dict) and "results" in result:
        return f"{len(result['results'])} results: " + "; ".join(r.get("url", "") for r in result["results"][:5])
    if isinstance(result, dict):
        return ", ".join(f"{k}={str(v)[:60]}" for k, v in result.items() if k != "opening_text")
    return str(result)[:200]


def _gemini_agent(system, task, tools, functions, max_turns, trace) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=0.2,
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(name=t["name"], description=t["description"],
                                      parameters_json_schema=t["parameters"]) for t in tools])],
        # We run the loop ourselves (not the SDK's automatic mode) so that every
        # tool call passes through _run_tool: whitelist check + audit log.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents = [types.Content(role="user", parts=[types.Part(text=task)])]
    for turn in range(1, max_turns + 1):
        _count_call()
        response = generate(client, model=config.GEMINI_MODEL, contents=contents, config=cfg)
        calls = response.function_calls or []
        if not calls:
            return response.text or ""
        contents.append(response.candidates[0].content)          # remember what the AI asked
        replies = [types.Part.from_function_response(
                       name=c.name, response=_run_tool(c.name, dict(c.args or {}), functions, trace, turn))
                   for c in calls]
        contents.append(types.Content(role="user", parts=replies))  # tell it what happened
    return _force_final(contents, cfg, client, trace)


def _force_final(contents, cfg, client, trace) -> str:
    """Out of turns: ask once more, with tools switched off, for the final answer."""
    from google.genai import types
    trace.append({"turn": "limit", "tool": "-", "input": {}, "status": "max_turns reached",
                  "result_summary": "asked the agent to finish with what it has"})
    _count_call()
    contents.append(types.Content(role="user", parts=[types.Part(
        text="You have used all your turns. Give your final JSON answer now with what you have.")]))
    final_cfg = types.GenerateContentConfig(system_instruction=cfg.system_instruction, temperature=0.2)
    return generate(client, model=config.GEMINI_MODEL, contents=contents, config=final_cfg).text or ""


def _bedrock_agent(system, task, tools, functions, max_turns, trace) -> str:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
    tool_config = {"tools": [{"toolSpec": {"name": t["name"], "description": t["description"],
                                           "inputSchema": {"json": t["parameters"]}}} for t in tools]}
    messages = [{"role": "user", "content": [{"text": task}]}]
    for turn in range(1, max_turns + 1):
        _count_call()
        r = client.converse(modelId=config.BEDROCK_MODEL, system=[{"text": system}], messages=messages,
                            toolConfig=tool_config, inferenceConfig={"maxTokens": 4096, "temperature": 0.2})
        reply = r["output"]["message"]
        messages.append(reply)
        if r["stopReason"] != "tool_use":
            return "".join(b.get("text", "") for b in reply["content"])
        results = []
        for block in reply["content"]:
            if "toolUse" in block:
                req = block["toolUse"]
                out = _run_tool(req["name"], req["input"], functions, trace, turn)
                results.append({"toolResult": {"toolUseId": req["toolUseId"],
                                               "content": [{"text": json.dumps(out)}]}})
        messages.append({"role": "user", "content": results})
    trace.append({"turn": "limit", "tool": "-", "input": {}, "status": "max_turns reached", "result_summary": ""})
    _count_call()
    messages.append({"role": "user", "content": [{"text": "You have used all your turns. Give your final JSON answer now."}]})
    r = client.converse(modelId=config.BEDROCK_MODEL, system=[{"text": system}], messages=messages,
                        toolConfig=tool_config, inferenceConfig={"maxTokens": 4096, "temperature": 0.2})
    return "".join(b.get("text", "") for b in r["output"]["message"]["content"])


def run_tool_agent(system: str, task: str, tools: list[dict], functions: dict,
                   max_turns: int, trace: list) -> str:
    """Run the agent loop with the configured provider. Returns the AI's final text.

    trace (a list) is filled with one entry per tool call - the agent's audit trail.
    """
    if config.LLM_PROVIDER == "gemini":
        return _gemini_agent(system, task, tools, functions, max_turns, trace)
    if config.LLM_PROVIDER == "bedrock":
        return _bedrock_agent(system, task, tools, functions, max_turns, trace)
    raise LLMUnavailable("Offline mode: no AI model configured.")