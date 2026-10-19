# Product: Liability Radar

## What it is
An agentic AI research assistant for a bank's **Internal Audit** team (sponsor: DBS Bank,
brief "Agentic AI for Audit – External Driver Researcher"). It collects official regulatory
documents, reads them, extracts cited findings, flags anything uncertain for a human, and
produces an approved, source-linked report.

## Focus for this proof of concept
- Topic: **scam and fraud liability: who pays when a customer is scammed?** Of particular
  interest is the gap between *unauthorised* transactions (e.g. phishing, covered by Singapore's
  Shared Responsibility Framework) and *authorised* transfers where the victim is tricked
  into paying (most scam losses).
- Jurisdictions: **Singapore** (primary), **United Kingdom**, **Australia**.
- Report sections: A. Regulatory developments; B. Industry developments; comparison table.

## What the agent does (team brief)
1. Scrapes official websites responsibly.
2. Reads documents and extracts findings.
3. Displays findings in a readable format.
4. Flags what it may be unsure of, using explicit criteria, for a human to decide (human in the loop).
5. Solves "where do we find the policies?" with a curated registry, a human-fed library and
   discovery search.

## Users
- **Internal auditor**: chooses sources, reviews findings, approves the report.
- **Audit manager**: relies on approved reports.
- **Technology / model risk reviewer**: checks the controls and audit trail.
- **Source curator (Person B)**: maintains the registry.

## Non-negotiables
1. Every finding quotes and cites a passage (with page) from a named source.
2. Source access goes through one gateway that enforces the whitelist, robots.txt and rate limits.
3. Code-based checks flag unsupported quotes and numbers; flags are shown, never hidden.
4. A report is DRAFT until a named human approves it; high-severity flags block approval.
5. Every run is logged: sources read or blocked, AI model, findings, every human decision.
6. All tools are read-only.

## Out of scope
Deciding individual compensation claims or calculating payouts (needs a bank's private
policies; possible future extension), and legal advice.
