# Experiments log: "Try approach A, checkpoint, try approach B, keep the best"

Each experiment compares two approaches on the **same inputs** and records the evidence for a
design decision.

How to checkpoint:
- **Within a Kiro session:** use Kiro's checkpoint and restore to roll back code changes while trying an approach.
- **Across sessions (permanent):** commit and tag in git, e.g. `git tag E1-A-single-agent`, so the
  group can always reproduce each approach and the report can cite it.
- Save the run logs from each approach (`runs/`) as evidence.

Standard test input unless stated otherwise: topic = scam and fraud liability; jurisdictions = SG, UK.
Metrics come from the eval script (T8.2): citation accuracy, answer accuracy vs gold set,
coverage, run time, approximate cost.

---

## E1. Single agent vs multi-agent pipeline (supports design decision D1)
- **Hypothesis:** the multi-agent pipeline gives better coverage and citation accuracy, at higher cost.
- **Approach A:** one agent with all tools (`step1_agent_loop.py`, extended). Git tag: `E1-A`
- **Approach B:** full pipeline. Git tag: `E1-B`
- **Results:**

| Metric | A | B |
|---|---|---|
| Citation accuracy | | |
| Answer accuracy | | |
| Jurisdictions covered | | |
| Run time | | |
| Cost | | |

- **Decision and reason:**

## E2. Snippets only vs snippets + full-document reading
- **Hypothesis:** reading full documents improves date and figure accuracy.
- **Approach A:** search snippets only. **Approach B:** search + `read_document`.
- **Results / decision:**

## E3. Verifier off vs on (supports design decision D6)
- **Hypothesis:** the verifier catches most unsupported claims before a human sees them.
- **Method:** plant 5 known-false claims in a report, then measure how many the verifier flags. Also
  measure the false-flag rate on true claims.
- **Results / decision:**

## E4. Model comparison on Bedrock (supports design decision D10)
- **Hypothesis:** a stronger model is more accurate, but a cheaper one is good enough for some agents (e.g. the Planner).
- **Approaches:** e.g. Amazon Nova Lite vs Nova Pro (and Claude, if budget allows). Only `MODEL` changes.
- **Results / decision:**

## E5. No-AI baseline vs AI extraction
- **Hypothesis:** AI extraction gives more useful, correctly categorised findings than offline keyword excerpts, without more high-severity flags.
- **Method:** same sources; run once with `LLM_PROVIDER=offline` and once with `gemini` (or Bedrock). Compare: findings judged useful by a reviewer, % with HIGH flags, gold-set coverage.
- **Results / decision:**
