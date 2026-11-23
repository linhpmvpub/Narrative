"""Conservative source-text roles; no identity merge, graph write or financial claim."""

import re

UNSAFE = re.compile(r'["“”]|\b(not|never|may|might|could|would|plans?|expect\w*|'
                    r'competitors?|said|says|according to|no longer)\b', re.I)
PURCHASE = re.compile(r"\bWe purchase (?P<product>[^.;!?\n]{2,120}?) from "
                      r"(?P<suppliers>[^;!?\n]{2,600}?)(?=\.(?:\s+(?:We|Our|The|This|It)\b|\s*$)|$)", re.I)
NETWORK = re.compile(r"\bWe (?:utilize|use|rely on|purchase)\b.{0,180}?"
                     r"\b(suppliers?|foundries|subcontractors?|contract manufacturers?|memory from)\b", re.I)
COMPETITION = re.compile(r"\bour competitors\b|\bWe face\b.{0,60}\bcompetition\b", re.I)


def valid_cik(value):
    return bool(value and str(value).isdigit() and int(value) > 0)


def extract_supply_roles(text, issuer_cik):
    """Only externally identified issuer-authored, affirmative bounded paragraphs."""
    if not valid_cik(issuer_cik) or not text or len(text) > 1600:
        return {"issuer_supply_context": False, "facts": [], "routing_withheld": False}
    if UNSAFE.search(text) or COMPETITION.search(text):
        # Rejecting role extraction must not fall back to broad economic co-occurrence.
        return {"issuer_supply_context": bool(NETWORK.search(text)), "facts": [],
                "routing_withheld": bool(NETWORK.search(text) or COMPETITION.search(text))}
    facts = []
    for match in PURCHASE.finditer(text):
        if re.search(r",|\band\b", match["product"], re.I):
            continue
        if re.search(r"\.\s+(?!and\b|or\b)[A-Z]", match["suppliers"]):
            continue  # Never borrow a company name from an adjacent sentence.
        if re.search(r"\b(affiliates?|subsidiar\w*|customers?|suppliers?|partners?)\b",
                     match["suppliers"], re.I):
            continue
        facts.append({"buyer_cik": str(int(issuer_cik)), "predicate": "PURCHASES_FROM",
            "product": match["product"], "supplier_text": match["suppliers"],
            "start": match.start(), "end": match.end(), "text": match.group(),
            "product_start": match.start("product"), "supplier_start": match.start("suppliers"),
            "identity_merged": False, "relationship_verified": False})
    return {"issuer_supply_context": bool(NETWORK.search(text) or facts), "facts": facts,
            "routing_withheld": False}


def supplier_span(fact, legal_name):
    """Multiword legal-name stem only; no ticker or single-word brand expansion."""
    words = re.findall(r"[a-z0-9]+", legal_name.casefold())
    while words and words[-1] in {"inc", "incorporated", "corp", "corporation", "ltd", "limited"}:
        words.pop()
    if len(words) < 2:
        return None
    expression = (r"(?<!\w)" + r"[\W_]+".join(re.escape(w) for w in words)
                  + r"(?:[\s,]+(?:Inc(?:orporated)?|Corp(?:oration)?|Ltd|Limited)\.?)?"
                    r"(?=\s*(?:,|\.|and\b|or\b|$))")
    match = re.search(expression, fact["supplier_text"], re.I)
    if not match:
        return None
    return {"start": fact["supplier_start"] + match.start(),
            "end": fact["supplier_start"] + match.end(), "text": match.group()}
