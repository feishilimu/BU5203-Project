# Experiments: try approach A, try approach B, keep the best

Checkpoint each approach with a git tag (e.g. `git tag E1-data-protection`) and keep the run
JSON files from `runs/` as evidence.

## E1. Which topic shows the tool's value best? (the sponsor asked for this)
- **Approaches:** the same engine on `data_protection`, `financial_crime` and `scams`, each
  with 3 jurisdictions.
- **Measure per topic:**

| Metric | Data protection | Financial crime | Scams |
|---|---|---|---|
| Relevant documents recommended / total recommended | | | |
| Documents with an effective date found (and ✓ verified) | | | |
| Comparison cells filled (not "Not stated") / total cells | | | |
| Reviewer verdict: is the comparison useful? (1–5) | | | |
| AI calls used | | | |

- **Decision and reason:**

## E2. Agent discovery vs keyword search
- **Approach A:** `LLM_PROVIDER=offline` (keyword fallback). **Approach B:** the AI agent.
- **Measure:** the share of recommendations a reviewer ticks as relevant; the number of key
  documents found (against Person B's list of must-find documents).

## E3. Date accuracy
- For 10 profiled documents, check the issue and effective dates by hand.
- **Measure:** correct / wrong / missed, and how many wrong dates the
  `date_not_in_document` check caught.

## E4. Q&A grounding
- Ask 10 questions (5 answerable from the document, 5 not).
- **Measure:** correct answers; correct "not in document" refusals; citations verified ✓.

## E5. Model comparison (once Bedrock is available)
- Gemini vs Bedrock (Nova / Claude): the same sources and questions. Compare E1–E4 metrics and cost.

## E6. Trend accuracy
- Profile 3 statistics documents (e.g. annual scam statistics for SG, HK and UK).
- Check 20 charted figures by hand against the PDF.
- **Measure:**
  - correct charted figures / total charted;
  - figures the AI extracted but code rejected (unverified), and how many of those were really wrong;
  - categories merged correctly across years (same name for the same thing).
- **Decision:** is the AI extraction good enough, or do we need a stricter prompt or model?
