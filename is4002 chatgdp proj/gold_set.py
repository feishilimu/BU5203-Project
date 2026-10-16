"""
gold_set.py
Known key regulatory developments per jurisdiction (the "gold set"), used by the
coverage checklist scoring (feature 2) and by Deep mode's templated gap queries
(feature 9a). Pure data + a small matching helper — no network, no LLM.

Each gold item: {id, description, keywords: [...]}. Keywords are lowercase
substrings that are matched case-insensitively against a claim haystack.
"""

GOLD_SET = {
    "Singapore": [
        {
            "id": "sg-srf",
            "description": "Shared Responsibility Framework (MAS + IMDA)",
            "keywords": ["shared responsibility framework", "srf", "mas", "imda"],
        },
        {
            "id": "sg-ecosystem",
            "description": "Anti-scam ecosystem measures (ATIP, Money Lock, kill switch)",
            "keywords": ["anti-scam", "scam", "atip", "money lock", "kill switch"],
        },
        {
            "id": "sg-ecommerce",
            "description": "E-commerce marketplace transaction safety ratings",
            "keywords": ["e-commerce", "ecommerce", "marketplace", "transaction safety"],
        },
    ],
    "United Kingdom": [
        {
            "id": "uk-app-reimbursement",
            "description": "PSR mandatory reimbursement of APP fraud",
            "keywords": [
                "app fraud",
                "authorised push payment",
                "mandatory reimbursement",
                "psr",
            ],
        },
        {
            "id": "uk-fca",
            "description": "FCA consumer protection / Consumer Duty on fraud",
            "keywords": ["fca", "consumer duty", "financial conduct authority"],
        },
        {
            "id": "uk-faster-payments",
            "description": "Faster Payments / Pay.UK reimbursement rules",
            "keywords": ["faster payments", "pay.uk", "reimbursement rules"],
        },
    ],
    "Australia": [
        {
            "id": "au-spf",
            "description": "Scams Prevention Framework",
            "keywords": ["scams prevention framework", "spf", "treasury", "accc"],
        },
        {
            "id": "au-asic",
            "description": "ASIC enforcement / bank anti-scam expectations",
            "keywords": ["asic", "australian securities", "enforcement"],
        },
        {
            "id": "au-nasc",
            "description": "National Anti-Scam Centre measures",
            "keywords": ["national anti-scam centre", "nasc", "anti-scam centre"],
        },
    ],
}


def gold_items_for(jurisdiction: str) -> list:
    """Return the list of gold items for a jurisdiction (empty list if none)."""
    return GOLD_SET.get(jurisdiction, [])
