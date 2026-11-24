"""Bounded own-issuer operating context; no attribution or financial-impact inference."""

import re

from engine.supply_roles import valid_cik

AMBIGUOUS = re.compile(
    r"\b(competitors?|rivals?|according to|said|says|reported by|they|their|"
    r"may|might|could|would|will|expect\w*|plans?|planned|planning|forecast\w*|anticipat\w*|"
    r"not|no|never|if|unless)\b", re.I)
OWN = re.compile(r"\b(we|our)\b", re.I)


def operating_matches(binding, text, issuer_cik, profile_cik):
    if (not valid_cik(issuer_cik) or not valid_cik(profile_cik)
            or int(issuer_cik) != int(profile_cik) or not text or len(text) > 1600
            or re.search(r'''["'“”‘’]''', text)):
        return []

    def literal(term):
        return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I)

    if any(literal(t).search(text) for t in binding.exclude_terms):
        return []
    # Periods within decimals remain in the original sentence; no normalization of offsets.
    for sentence in re.finditer(r"[^.!?]+(?:\.(?=\d)[^.!?]+)*(?:[.!?]|$)", text):
        segment = sentence.group()
        own = OWN.search(segment)
        if not own or AMBIGUOUS.search(segment):
            continue
        spans = []
        for group in ("topic_terms", "context_terms", "change_terms"):
            found = next(((term, hit) for term in getattr(binding, group)
                          if (hit := literal(term).search(segment))), None)
            if found is None:
                break
            term, hit = found
            spans.append({"group": group, "field": "summary", "term": term,
                "start": sentence.start() + hit.start(), "end": sentence.start() + hit.end(),
                "text": hit.group(), "matched_term": term, "alias_used": False})
        if len(spans) == 3:
            return spans + [{"group": "issuer_subject", "field": "summary",
                "start": sentence.start() + own.start(), "end": sentence.start() + own.end(),
                "text": own.group()}, {"group": "operating_sentence", "field": "summary",
                "start": sentence.start(), "end": sentence.end(), "text": segment,
                "identity_merged": False, "impact_eligible": False}]
    return []


def shipment_matches(binding, text, issuer_cik, profile_cik):
    """Exact issuer-disclosed shipment bullet, never a foundry/capacity assertion."""
    if (not valid_cik(issuer_cik) or not valid_cik(profile_cik)
            or int(issuer_cik) != int(profile_cik) or not text or len(text) > 1600
            or re.search(r"[\"'“”‘’]", text) or AMBIGUOUS.search(text)
            or re.search(r"\b(cancel\w*|delay\w*|halt\w*|scheduled|target\w*|on track)\b", text, re.I)):
        return []
    if any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", text, re.I)
           for t in binding.exclude_terms):
        return []
    for phrase in binding.context_terms:
        if not any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", phrase, re.I)
                   for t in binding.topic_terms):
            continue
        match = re.search(r"(?:^|[.!?;•‒ƒ\n])\s*(?P<claim>" + re.escape(phrase)
                          + r")(?!\w)", text, re.I)
        if match:
            start, end = match.span("claim")
            return [{"group": "product_shipment_phrase", "field": "summary",
                "start": start, "end": end, "text": text[start:end],
                "matched_term": phrase, "alias_used": False,
                "identity_merged": False, "impact_eligible": False,
                "foundry_exposure_verified": False}]
    return []
