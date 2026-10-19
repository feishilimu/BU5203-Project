"""
llm.py - one doorway to whichever AI model ("LLM") we use.

KEY IDEA
The rest of the code calls ONE function, ask_json(system, prompt), and doesn't
care which AI answers. Switching between Google Gemini, Amazon Bedrock or
"offline" is a one-line change in .env (LLM_PROVIDER). That's a design decision
worth defending: no lock-in, and you can compare models fairly (experiment E4).

GOVERNANCE NOTE
Gemini's FREE tier terms allow Google to use prompts to improve its products,
and human reviewers may read them. That's acceptable here ONLY because we send
public regulatory documents. A bank would use a paid tier or Amazon Bedrock,
where data stays under its own contracts and AWS account.

ALSO HERE
  - a disk cache: the same prompt is never paid for twice (re-runs are free)
  - a call counter + limit: a hard stop if a run makes too many AI calls
"""
import hashlib
import json
import re

import config

_CACHE = config.CACHE_DIR / "llm"
_CACHE.mkdir(exist_ok=True)

calls_made = 0  # calls in the current run (reset by the pipeline)


class LLMUnavailable(Exception):
    """Raised in offline mode, or when the call limit is reached."""


def describe() -> str:
    if config.LLM_PROVIDER == "gemini":
        return f"Google Gemini ({config.GEMINI_MODEL})"
    if config.LLM_PROVIDER == "bedrock":
        return f"Amazon Bedrock ({config.BEDROCK_MODEL})"
    return "Offline (no AI - keyword extraction only)"


def model_name() -> str:
    return {"gemini": config.GEMINI_MODEL, "bedrock": config.BEDROCK_MODEL}.get(config.LLM_PROVIDER, "none")


# ---------------------------------------------------------------------------
# Provider-specific calls: each takes (system, prompt) and returns text.
# ---------------------------------------------------------------------------
def _gemini(system: str, prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.1,                         # low = stick to the text, less creative
            response_mime_type="application/json",   # ask Gemini for JSON only
        ),
    )
    return response.text or ""


def _bedrock(system: str, prompt: str) -> str:
    import boto3  # uses the Bedrock API key in AWS_BEARER_TOKEN_BEDROCK

    client = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
    response = client.converse(
        modelId=config.BEDROCK_MODEL,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
    )
    return "".join(b.get("text", "") for b in response["output"]["message"]["content"])


# ---------------------------------------------------------------------------
# The one function everyone uses
# ---------------------------------------------------------------------------
def ask_json(system: str, prompt: str):
    """Send a prompt, return the parsed JSON answer (dict or list).

    Raises LLMUnavailable in offline mode or when the per-run limit is hit.
    """
    global calls_made
    if config.LLM_PROVIDER not in ("gemini", "bedrock"):
        raise LLMUnavailable("Offline mode: no AI model configured.")

    key = hashlib.sha256(f"{config.LLM_PROVIDER}|{model_name()}|{system}|{prompt}".encode()).hexdigest()
    cached = _CACHE / f"{key[:32]}.json"
    if cached.exists():
        return json.loads(cached.read_text())["answer"]

    if calls_made >= config.MAX_LLM_CALLS_PER_RUN:
        raise LLMUnavailable(f"Run limit of {config.MAX_LLM_CALLS_PER_RUN} AI calls reached (kill switch).")
    calls_made += 1

    text = _gemini(system, prompt) if config.LLM_PROVIDER == "gemini" else _bedrock(system, prompt)
    answer = parse_json(text)
    cached.write_text(json.dumps({"answer": answer}))
    return answer


def parse_json(text: str):
    """Models sometimes wrap JSON in ```fences``` or add a sentence. Be forgiving."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)  # first {...} or [...] block
        if match:
            return json.loads(match.group(1))
        raise
