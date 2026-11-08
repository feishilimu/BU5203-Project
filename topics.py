"""
topics.py - TOPIC PACKS: everything that differs from one topic to another.

WHY THIS FILE EXISTS (sponsor feedback)
"Scam liability is too narrow" and "comparison tables suit topics like data
protection, where rules differ across DBS's markets". So the engine no longer
knows any topic. A topic pack tells it:

  domains      which official regulator websites to search, per jurisdiction
               (the user can add more in the app - e.g. "just give it mas.gov.sg")
  questions    the comparison questions - the ROWS of the comparison table
  areas        internal bank areas a rule can affect - "map to internal"
  keywords     words that signal a relevant passage (weight -> strength)
  queries      starter searches, used if the AI agent is unavailable
  statistics   what statistics the agent should look for (for trend charts),
               plus any extra statistics sites (e.g. an industry body - shown
               as a SECONDARY source because it isn't a regulator)
  report_sections  which views the report shows, IN WHICH ORDER - each topic
               gets the report that suits it (e.g. trends matter for scams,
               the comparison matters for data protection)

To add a topic: copy a pack, change the values. No other code changes.
Run the same engine on several packs and compare which gives the most useful
output - the sponsor's "experiment to see which results in the best outcome".
"""

TOPICS = {
    # -----------------------------------------------------------------------
    "data_protection": {
        "name": "Personal data protection & cross-border data transfer",
        "description": "Rules on collecting, using, contacting customers about, protecting and "
                       "transferring personal data across borders - where DBS's markets differ most.",
        "default_jurisdictions": ["Singapore", "Hong Kong", "India"],
        "domains": {
            "Singapore": ["pdpc.gov.sg", "mas.gov.sg", "sso.agc.gov.sg"],
            "Hong Kong": ["pcpd.org.hk", "hkma.gov.hk", "elegislation.gov.hk"],
            "India": ["meity.gov.in", "rbi.org.in"],
            "Indonesia": ["ojk.go.id", "komdigi.go.id", "peraturan.bpk.go.id"],
            "China": ["cac.gov.cn", "pbc.gov.cn"],
        },
        "language_notes": {
            "Indonesia": "Many documents are in Bahasa Indonesia; the AI translates, so check key terms.",
            "China": "Most documents are in Chinese; the AI translates, so check key terms.",
        },
        "questions": [
            "Main law and regulator",
            "Cross-border transfer of personal data",
            "Data localisation (must data stay in-country?)",
            "Consent / legal basis for processing",
            "Breach notification deadline",
            "Direct marketing and contacting customers",
            "Data protection officer required?",
            "Maximum penalty",
        ],
        "areas": ["Retail & consumer banking", "Marketing & customer contact",
                  "IT, cloud & outsourcing", "Cross-border shared services",
                  "Cybersecurity & incident response", "HR & employee data", "Compliance / DPO"],
        "keywords": {
            3: ["personal data", "cross-border", "transfer", "localis", "localiz", "breach",
                "notif", "consent", "data protection", "data subject", "do not call", "dnc"],
            2: ["effective", "commence", "come into force", "comes into operation", "amend",
                "guideline", "penalt", "fine", "obligation", "officer", "outsourc", "cloud"],
            1: ["bank", "financial institution", "customer", "organisation", "organization"],
        },
        "report_sections": ["key_dates", "comparison", "trends_if_found", "profiles"],
        "statistics": {
            "what": "statistics on data breach notifications, complaints, and enforcement actions or "
                    "financial penalties, by year",
            "metrics_hint": ["breach notifications", "complaints received", "enforcement decisions", "penalties"],
            "category_hint": "type of breach / sector / outcome",
            "domains": {},
        },
        "queries": [
            "{j} personal data protection law cross-border transfer requirements",
            "{j} data breach notification deadline financial institutions",
            "{j} personal data protection amendment guidelines 2026",
            "{j} personal data protection act full text pdf",
        ],
    },
    # -----------------------------------------------------------------------
    "financial_crime": {
        "name": "Financial crime: anti-money laundering (AML/CFT)",
        "description": "Customer due diligence, suspicious transaction reporting, beneficial "
                       "ownership, virtual assets and sanctions across DBS's markets.",
        "default_jurisdictions": ["Singapore", "Hong Kong", "India"],
        "domains": {
            "Singapore": ["mas.gov.sg", "police.gov.sg", "sso.agc.gov.sg"],
            "Hong Kong": ["hkma.gov.hk", "sfc.hk", "jfiu.gov.hk"],
            "India": ["rbi.org.in", "fiuindia.gov.in"],
            "Indonesia": ["ojk.go.id", "ppatk.go.id"],
        },
        "language_notes": {
            "Indonesia": "Many documents are in Bahasa Indonesia; the AI translates, so check key terms.",
        },
        "questions": [
            "Main law and regulator",
            "Customer due diligence (KYC) requirements",
            "Beneficial ownership",
            "Suspicious transaction reporting",
            "Record keeping period",
            "Virtual assets / crypto (incl. travel rule)",
            "Sanctions screening",
            "Maximum penalty",
        ],
        "areas": ["Retail onboarding & KYC", "Corporate & institutional banking",
                  "Transaction monitoring", "Trade finance", "Correspondent banking",
                  "Digital assets", "Compliance / MLRO"],
        "keywords": {
            3: ["money laundering", "terrorism financing", "customer due diligence", "cdd", "kyc",
                "suspicious transaction", "beneficial owner", "travel rule", "virtual asset",
                "sanction", "proliferation"],
            2: ["effective", "commence", "come into force", "notice", "guideline", "record",
                "penalt", "fine", "amend", "risk assessment", "screening"],
            1: ["bank", "financial institution", "customer", "transaction"],
        },
        "report_sections": ["key_dates", "obligations", "trends", "comparison", "profiles"],
        "statistics": {
            "what": "statistics on suspicious transaction reports filed, money laundering investigations, "
                    "prosecutions or convictions, and enforcement actions / penalties, by year",
            "metrics_hint": ["suspicious transaction reports", "money laundering cases", "penalties imposed"],
            "category_hint": "reporting sector / offence type",
            "domains": {"Hong Kong": ["jfiu.gov.hk"], "India": ["fiuindia.gov.in"]},
        },
        "queries": [
            "{j} anti-money laundering notice banks customer due diligence",
            "{j} suspicious transaction reporting requirements banks",
            "{j} AML CFT amendments 2026 virtual assets",
        ],
    },
    # -----------------------------------------------------------------------
    "scams": {
        "name": "Scams & fraud liability",
        "description": "Who bears the loss when a customer is scammed, and the duties of banks "
                       "and telcos. Kept from v1 for comparison.",
        "default_jurisdictions": ["Singapore", "United Kingdom", "Australia"],
        "domains": {
            "Singapore": ["mas.gov.sg", "imda.gov.sg", "police.gov.sg"],
            "United Kingdom": ["psr.org.uk", "fca.org.uk", "gov.uk"],
            "Australia": ["treasury.gov.au", "accc.gov.au", "legislation.gov.au", "scamwatch.gov.au"],
        },
        "language_notes": {},
        "questions": [
            "Which scams are covered",
            "Who bears the loss",
            "Reimbursement cap or excess",
            "Claims process and timeline",
            "Duties on banks",
            "Upcoming changes",
        ],
        "areas": ["Fraud operations", "Digital banking", "Customer service & claims",
                  "Customer communications", "Compliance"],
        "keywords": {
            3: ["bear the loss", "bear any loss", "reimburse", "compensat", "liable", "refund",
                "shared responsibility", "authorised push payment", "app fraud", "self-effected",
                "seemingly authorised", "unauthorised transaction"],
            2: ["scam", "fraud", "phishing", "duty", "duties", "effective", "commence", "claim",
                "consultation", "maximum", "excess"],
            1: ["bank", "financial institution", "telco", "customer", "victim"],
        },
        "report_sections": ["key_dates", "trends", "comparison", "profiles"],
        "statistics": {
            "what": "official scam statistics by scam type - number of cases and amounts lost - for several "
                    "periods (annual and mid-year scam and cybercrime statistics)",
            "metrics_hint": ["number of cases", "amount lost"],
            "category_hint": "scam type (e.g. investment, job, phishing, government official impersonation)",
            # Industry bodies publish the UK's main fraud statistics: allowed, but labelled secondary.
            "domains": {"United Kingdom": ["ukfinance.org.uk"]},
        },
        "queries": [
            "{j} scam victim reimbursement bank liability rules",
            "{j} shared responsibility scam losses banks guidelines",
        ],
    },
}

DEFAULT_TOPIC = "data_protection"

# What each report section is called (used by the app tabs and the Markdown report).
SECTION_TITLES = {
    "key_dates": "Key dates",
    "comparison": "Compare jurisdictions",
    "trends": "Trends",
    "trends_if_found": "Trends",
    "obligations": "Key obligations",
    "profiles": "Document profiles",
}


def get(topic_id: str) -> dict:
    return TOPICS[topic_id]


def domains_for(topic_id: str, jurisdiction: str, extra: list[str] | None = None) -> list[str]:
    """Domains the agent may search: official ones, statistics sites, plus any the user added."""
    pack = TOPICS[topic_id]
    return sorted(set(pack["domains"].get(jurisdiction, [])
                      + pack.get("statistics", {}).get("domains", {}).get(jurisdiction, [])
                      + (extra or [])))
