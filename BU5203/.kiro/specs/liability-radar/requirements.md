# Requirements: Liability Radar

## Introduction
Internal auditors at DBS must stay current on external regulatory and industry developments
before fieldwork. Today this is manual, slow and hard to scale across jurisdictions. Liability
Radar is an agentic AI solution that researches a chosen topic across selected jurisdictions and
produces a structured, source-cited report for auditor review.

**PoC topic:** scam and fraud liability.

Acceptance criteria use **EARS** notation (WHEN / IF / WHILE ... THE SYSTEM SHALL ...), the format
Kiro uses, so each one can be tested.

Each requirement is tagged with the course **controls table** row it implements
(Scope, Permissions, Checkpoints, Audit trail, Kill switch, Blast radius), so evaluators can trace
intent → control → code.

## Glossary
- **Run**: one execution of the pipeline for a topic and set of jurisdictions.
- **Claim**: a single factual statement in the report.
- **Trusted source**: a domain on the whitelist in `config.py` (regulator, government, legislation).
- **Tier 1 / Tier 2 source**: Tier 1 = trusted official source; Tier 2 = any other site (news, industry).
- **Regulatory Sources MCP server**: the only component allowed to reach external sources.
- **Draft / Approved**: report status before and after human sign-off.

---

## Requirement 1: Configure a research run
**User story:** As an internal auditor, I want to choose a topic and the jurisdictions I care
about, so that the research matches the scope of my upcoming audit.

**Acceptance criteria**
1. THE SYSTEM SHALL let the user select a topic from a predefined list (PoC: "Scam and fraud liability").
2. THE SYSTEM SHALL let the user select one or more jurisdictions from those configured in `config.py`.
3. WHEN the user starts a run with no jurisdiction selected, THE SYSTEM SHALL block the run and show a message.
4. THE SYSTEM SHALL display the sources it will read before research starts, and the user SHALL choose which ones to include (see Requirement 16).

## Requirement 2: Research regulatory developments (Report Section A)
**User story:** As an internal auditor, I want new, amended and upcoming regulations summarised
in business language, so that I know which obligations the bank must now meet.

**Acceptance criteria**
1. FOR each selected jurisdiction, THE SYSTEM SHALL identify relevant regulations, guidelines, consultation papers, enforcement actions and policy statements.
2. FOR each development, THE SYSTEM SHALL record: title, issuing body, status (in force / upcoming / proposed / consultation), key dates (issued, effective, compliance deadline), key obligations and source URL.
3. THE SYSTEM SHALL summarise obligations in plain business language of no more than 3 sentences per development.
4. FOR each development, THE SYSTEM SHALL assess impact on the bank: risks, opportunities and suggested actions.
5. THE SYSTEM SHALL classify status relative to the run date supplied to the agents (agents are told today's date).

## Requirement 3: Research industry developments (Report Section B)
**User story:** As an internal auditor, I want to see major incidents, industry news and emerging
practices, so that I understand how peers and the market are responding.

**Acceptance criteria**
1. THE SYSTEM SHALL identify notable incidents, case studies and industry practices related to the topic.
2. THE SYSTEM SHALL label every industry item with its source tier (Tier 1 or Tier 2).
3. THE SYSTEM SHALL keep industry items visually separate from regulatory items.

## Requirement 4: Cross-jurisdiction comparison
**User story:** As an audit manager, I want a side-by-side comparison across jurisdictions, so that
I can see where DBS's home rules differ from other markets.

**Acceptance criteria**
1. THE SYSTEM SHALL produce a comparison table with these dimensions: who bears the loss; scams covered; conditions for reimbursement; caps or limits; duties on banks; duties on other parties (e.g. telcos); effective date.
2. EVERY non-empty cell in the table SHALL cite at least one source.
3. WHERE no information is found for a cell, THE SYSTEM SHALL show "Not found" rather than leave it blank or guess.

## Requirement 5: Source traceability *(Control: Audit trail)*
**User story:** As an internal auditor, I want every claim linked to its source, so that I can verify
it myself before relying on it in an audit.

**Acceptance criteria**
1. EVERY claim in the report SHALL include at least one source URL and the date the source was retrieved.
2. THE SYSTEM SHALL retain a cached copy of every source used, so that the evidence remains available even if the web page changes.
3. WHEN the user clicks a citation, THE SYSTEM SHALL show the source passage that supports the claim.

## Requirement 6: Source discipline via MCP *(Controls: Scope, Permissions)*
**User story:** As a technology risk reviewer, I want the sources the agents can use to be
defined in one controlled place, so that the bank decides what the AI may read, not the AI.

**Acceptance criteria**
1. THE SYSTEM SHALL route all external source access through the Regulatory Sources MCP server.
2. Agents SHALL NOT contain any code that accesses the network directly.
3. WHEN searching in "official" mode, THE MCP SERVER SHALL return only results from whitelisted domains, enforcing the whitelist in its own code rather than relying on the search engine.
4. THE MCP SERVER SHALL expose read-only tools only. No tool may send, post, modify or delete anything.
5. THE MCP SERVER SHALL expose a `list_trusted_sources` tool so that the whitelist is inspectable at run time.
6. WHEN the tool administrator adds or removes a trusted domain in `config.py`, THE SYSTEM SHALL apply the change on the next run without code changes elsewhere.

## Requirement 7: Responsible web access *(Control: Blast radius)*
**User story:** As a tool administrator, I want the tool to access public websites responsibly,
so that the bank is not exposed to legal, reputational or blocking risk.

**Acceptance criteria**
1. BEFORE fetching any page, THE MCP SERVER SHALL check the site's robots.txt and SHALL skip pages that are disallowed.
2. THE MCP SERVER SHALL wait at least 2 seconds between requests to the same domain.
3. THE MCP SERVER SHALL identify itself with an honest User-Agent string.
4. THE MCP SERVER SHALL serve repeat requests for the same URL from the local cache.

## Requirement 8: Claim verification and hallucination detection
**User story:** As an internal auditor, I want unsupported claims flagged, so that I don't rely on
something the AI invented.

**Acceptance criteria**
1. AFTER research, A VERIFIER AGENT that did not write the claims SHALL check every claim against the text of its cited source.
2. THE VERIFIER SHALL label each claim **Supported**, **Partially supported** or **Not supported**, with the quoted source passage as evidence.
3. IF a claim is Not supported, THEN THE SYSTEM SHALL keep it in the report, visibly flagged, and SHALL NOT silently remove it.
4. THE REPORT SHALL show a verification summary (e.g. "41 of 45 claims supported").
5. WHERE a numeric value or date appears in a claim, THE VERIFIER SHALL check that the exact value appears in the source.

## Requirement 9: Coverage completeness
**User story:** As an audit manager, I want to know that every selected jurisdiction was actually
researched, so that a gap isn't mistaken for "nothing happened".

**Acceptance criteria**
1. FOR every selected jurisdiction and report section, THE SYSTEM SHALL show either findings or an explicit "No developments found in sources searched", plus the searches performed.
2. THE SYSTEM SHALL show a coverage summary listing, per jurisdiction, the number of sources consulted and claims made.

## Requirement 10: Human checkpoint *(Control: Checkpoints)*
**User story:** As an audit manager, I want a human auditor to approve the report before it is
used, so that accountability stays with a person ("agents draft, humans merge").

**Acceptance criteria**
1. EVERY newly generated report SHALL have status **Draft**.
2. THE SYSTEM SHALL let the auditor accept, edit or reject individual claims.
3. WHEN the auditor approves, THE SYSTEM SHALL record the approver's name and timestamp and set status to **Approved**.
4. A Draft report SHALL be visibly watermarked "DRAFT – NOT FOR RELIANCE".

## Requirement 11: Audit trail and reproducibility *(Control: Audit trail)*
**User story:** As a technology risk reviewer, I want every run fully logged, so that I can answer
"which agent, which version, whose approval?"

**Acceptance criteria**
1. FOR every run, THE SYSTEM SHALL save a log containing: run ID, timestamp, user inputs, model name, prompt versions, every agent step, every MCP tool call (inputs, outputs, URLs), verification results and approval record.
2. THE SYSTEM SHALL let a reviewer open any past run and see its full trace in the UI.
3. Logs SHALL be append-only: the app SHALL NOT offer a way to edit a past log.

## Requirement 12: Limits and kill switch *(Control: Kill switch)*
**User story:** As a technology risk reviewer, I want hard limits and a stop button, so that a
confused agent cannot run away with cost or time.

**Acceptance criteria**
1. EACH agent SHALL stop after a configurable maximum number of turns.
2. EACH run SHALL stop when it exceeds a configurable maximum number of tool calls or wall-clock time.
3. THE UI SHALL provide a Stop button that halts all agents and saves the partial log.
4. WHEN a limit is hit, THE SYSTEM SHALL record which limit and show partial results marked incomplete.

## Requirement 13: Prompt-injection resilience *(Control: Blast radius)*
**User story:** As a technology risk reviewer, I want web content treated as data, not
instructions, so that a malicious page cannot hijack the agents.

**Acceptance criteria**
1. THE SYSTEM SHALL wrap all fetched content in clearly delimited "untrusted source content" markers before passing it to an agent.
2. Agent instructions SHALL state that text inside source content must never be followed as instructions.
3. Because all tools are read-only (Req 6.4), THE WORST CASE of a successful injection SHALL be a wrong claim, which the verifier and human checkpoint are designed to catch.

## Requirement 14: Explainability
**User story:** As an internal auditor, I want to see how the report was produced, so that I can
explain and defend it to my manager or a regulator.

**Acceptance criteria**
1. EACH agent SHALL return structured output (a validated data model), not free text.
2. THE UI SHALL let the user inspect each agent's output: plan, findings per jurisdiction, analysis, verification.
3. EACH claim SHALL show its reasoning trail: which agent produced it, from which source, and its verification result.

## Requirement 15: Evaluation
**User story:** As the project team, we want to measure accuracy against known answers, so that
we can show evidence rather than impressions.

**Acceptance criteria**
1. THE SYSTEM SHALL provide an evaluation script that runs the pipeline against the gold question set in `eval/` (owned by Person B).
2. THE SCRIPT SHALL report: citation accuracy (% claims supported), answer accuracy vs gold answers, jurisdiction coverage, run time and approximate cost.
3. Results SHALL be saved per run so that experiments (`docs/experiments.md`) can be compared.

## Requirement 16: Finding the right sources, with a human deciding *(Controls: Scope, Checkpoints)*
**User story:** As an internal auditor, I want the key official documents (such as victim
compensation rules) to be found reliably, and to decide myself which sources the agent reads,
so that important rules aren't missed and nothing unvetted gets into the report.

**Acceptance criteria**
1. THE SYSTEM SHALL provide a curated registry of official documents per jurisdiction, each with a reason it matters.
2. THE SYSTEM SHALL let a user upload a document to a library (for documents the scraper can't reach or that aren't public), recording who added it and when.
3. WHEN discovery search returns results, THE SYSTEM SHALL add them unticked, and SHALL only read them after a user ticks them.
4. THE SYSTEM SHALL read whole documents (not only the first pages) and select the passages most relevant to the topic.
5. WHEN a source can't be read (robots.txt, unreachable, refused), THE SYSTEM SHALL record why and show it in the coverage summary.
