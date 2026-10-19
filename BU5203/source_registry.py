"""
source_registry.py - a curated list of KNOWN official sources.

THE PROBLEM THIS SOLVES ("where would they find the policies?")
Open web search is unreliable for finding the key rules. The documents that
matter most (e.g. MAS's Shared Responsibility Framework guidelines) are often
PDFs buried deep in regulator websites, and search engines may not rank them.

So we use THREE ways to get sources, from most to least reliable:
  1. This registry   - a reviewed list of official documents per country.
                       A human (Person B) curates it; the agent reads them.
  2. The library     - documents a human uploads by hand (e.g. a PDF you
                       downloaded yourself, or, in real life, the bank's own
                       internal compensation policy, which is never public).
  3. Discovery       - a web search limited to official domains, used to spot
                       NEW documents. Results only become sources after a
                       human ticks them (human-in-the-loop).

HOW TO ADD A SOURCE
Copy an entry, give it a unique id, and fill in the fields. Before adding a
website, look at its terms of use and robots.txt and note anything relevant
in "notes" - see docs/responsible_scraping.md.

FIELDS
  id            unique short name
  jurisdiction  one of config.JURISDICTIONS
  title         human-readable title
  url           the official web address (always kept, even for local files,
                so the report can link to the original)
  local_file    optional: a manually downloaded copy in library/. If that file
                exists it is read INSTEAD of the website (use this when a site
                blocks bots - never try to get around the block). If it doesn't
                exist yet, the website is tried as normal.
  publisher     who issued it
  kind          regulation | guideline | statement | consultation | statistics | news | analysis
  section       "A" = regulatory development, "B" = industry development
  why           why an auditor should care (shown in the app)
"""

REGISTRY = [
    # ------------------------------------------------------------- SINGAPORE
    {
        "id": "sg-srf-guidelines",
        "jurisdiction": "Singapore",
        "title": "Guidelines on Shared Responsibility Framework (MAS & IMDA)",
        "url": "https://www.mas.gov.sg/regulation/guidelines/guidelines-on-shared-responsibility-framework",
        "local_file": "Guidelines_on_Shared_Responsibility_Framework.pdf",
        "publisher": "Monetary Authority of Singapore / IMDA",
        "kind": "guideline",
        "section": "A",
        "why": "The core rules: which scams are covered, bank and telco duties, and who bears the loss (Section 6).",
    },
    {
        "id": "sg-pq-authorised-transfers",
        "jurisdiction": "Singapore",
        "title": "MAS oral reply: adapting shared responsibility to authorised-transfer scams (Sep 2026)",
        "url": "https://www.mas.gov.sg/news/parliamentary-replies/2026/oral-reply-to-parliamentary-question-on-adapting-shared-responsibility-to-authorised-transfer-scams",
        "local_file": "MAS_PQ_authorised_transfers_2026.pdf",  # manual copy (site blocks bots / landing page only)
        "publisher": "Monetary Authority of Singapore",
        "kind": "statement",
        "section": "A",
        "why": "States whether the SRF will extend to scams where victims authorise the transfer themselves.",
    },
    {
        "id": "sg-srf-implementation",
        "jurisdiction": "Singapore",
        "title": "MAS and IMDA announce implementation of the SRF from 16 December 2024",
        "url": "https://www.mas.gov.sg/news/media-releases/2024/mas-and-imda-announce-implementation-of-shared-responsibility-framework-from-16-december-2024",
        "local_file": "MAS_SRF_implementation_2024.pdf",  # manual copy (site blocks bots / landing page only)
        "publisher": "Monetary Authority of Singapore",
        "kind": "statement",
        "section": "A",
        "why": "Effective date and what changed after public consultation.",
    },
    {
        "id": "sg-eupg",
        "jurisdiction": "Singapore",
        "title": "E-Payments User Protection Guidelines",
        "url": "https://www.mas.gov.sg/regulation/guidelines/e-payments-user-protection-guidelines",
        "local_file": "MAS_EUPG.pdf",  # manual copy (site blocks bots / landing page only)
        "publisher": "Monetary Authority of Singapore",
        "kind": "guideline",
        "section": "A",
        "why": "The SRF builds on these duties; covers liability for unauthorised transactions generally.",
    },
    {
        "id": "sg-combatting-scams",
        "jurisdiction": "Singapore",
        "title": "MAS: Combatting Scams",
        "url": "https://www.mas.gov.sg/regulation/combatting-scams",
        "local_file": "MAS_Combatting_Scams.pdf",  # manual copy (site blocks bots / landing page only)
        "publisher": "Monetary Authority of Singapore",
        "kind": "statement",
        "section": "A",
        "why": "MAS's overview of anti-scam measures and links to the latest documents.",
    },
    {
        "id": "sg-spf-scam-stats-2025",
        "jurisdiction": "Singapore",
        "title": "SPF: Scams and cybercrime fell by almost a quarter in 2025",
        "url": "https://www.police.gov.sg/media-hub/police-life/2026/02/scams-and-cybercrime-fell-by-almost-a-quarter-in-2025",
        "publisher": "Singapore Police Force",
        "kind": "statistics",
        "section": "B",
        "why": "Scale of the problem, including the share of self-effected (authorised) transfers.",
    },
    # -------------------------------------------------------- UNITED KINGDOM
    {
        "id": "uk-psr-app-protections",
        "jurisdiction": "United Kingdom",
        "title": "PSR: APP fraud reimbursement protections (consumer information)",
        "url": "https://www.psr.org.uk/information-for-consumers/app-fraud-reimbursement-protections/",
        "publisher": "Payment Systems Regulator",
        "kind": "regulation",
        "section": "A",
        "why": "The UK's mandatory reimbursement for authorised push payment (APP) scams.",
    },
    {
        "id": "uk-psr-one-year-on",
        "jurisdiction": "United Kingdom",
        "title": "PSR: One year on - impact of APP reimbursement on victims",
        "url": "https://www.psr.org.uk/news-and-updates/latest-news/news/one-year-on-impact-of-app-reimbursement-on-victims/",
        "publisher": "Payment Systems Regulator",
        "kind": "statement",
        "section": "A",
        "why": "Evidence on outcomes and the regulator's next steps.",
    },
    {
        "id": "uk-regtomorrow-73m",
        "jurisdiction": "United Kingdom",
        "title": "Regulation Tomorrow: Payment fraud falls by £73m following PSR reimbursement scheme",
        "url": "https://www.regulationtomorrow.com/2026/07/payment-fraud-falls-by-73m-following-psr-reimbursement-scheme/",
        "local_file": "RegulationTomorrow_PSR_73m.pdf",  # manual copy (site blocks bots / landing page only)
        "publisher": "Regulation Tomorrow (law firm blog)",
        "kind": "analysis",
        "section": "B",
        "why": "Secondary summary of the PSR evaluation, including the planned consultation.",
    },
    # ------------------------------------------------------------- AUSTRALIA
    {
        "id": "au-spf-rules-2026",
        "jurisdiction": "Australia",
        "title": "Competition and Consumer (Scams Prevention Framework) Rules 2026",
        "url": "https://www.legislation.gov.au/F2026L01140/asmade",
        "local_file": "AU_Scams_Prevention_Framework_Rules_2026.pdf",  # manual copy (site blocks bots / landing page only)
        "publisher": "Federal Register of Legislation (Australian Government)",
        "kind": "regulation",
        "section": "A",
        "why": "Australia's new framework of obligations on banks, telcos and digital platforms.",
    },
    {
        "id": "au-bakermckenzie-spf",
        "jurisdiction": "Australia",
        "title": "Baker McKenzie: Australia scams prevention draft code and rules released",
        "url": "https://www.bakermckenzie.com/en/insight/publications/2026/06/australia-scams-prevention-draft-code-and-rules-released",
        "local_file": "BakerMcKenzie_SPF_2026.pdf",  # manual copy (site blocks bots / landing page only)
        "publisher": "Baker McKenzie (law firm)",
        "kind": "analysis",
        "section": "B",
        "why": "Secondary explanation of the draft codes and rules for banks.",
    },
]


def sources_for(jurisdictions: list[str]) -> list[dict]:
    """Registry entries for the chosen countries."""
    return [s for s in REGISTRY if s["jurisdiction"] in jurisdictions]


def find(source_id: str) -> dict | None:
    return next((s for s in REGISTRY if s["id"] == source_id), None)