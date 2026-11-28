"""Source-reported compute access restrictions over an opt-in sourced route."""

import re

from engine.source_sentences import sentences

VERSION = "access-constraints-v1"
RESOURCE = r"\b(?:GPUs?|AI chips?|compute|computing capacity|AI infrastructure)\b"
ACTION = r"\b(?:restrict(?:s|ed)?|curb(?:s|ed)?|tighten(?:s|ed)?|ban(?:s|ned)?)\b"
BOUNDARY = r"[,;!?]|\b(?:and|but|whereas|while)\b"


def span(text, start, end):
    return {"text": text[start:end], "start": start, "end": end}


def classify(text):
    if len(text) > 1200 or re.search(r"\b(?:not|never|denied|could|might|may|would|if|unless|rumou?r|hypothetical)\b", text, re.I) or "?" in text:
        return None
    requirement = re.search(r"\b(?:told|required|ordered)\s+to\s+(?:rule out|exclude)\b", text, re.I)
    actions = list(re.finditer(ACTION, text, re.I))
    if requirement:
        actions.append(requirement)
    for action in actions:
        for resource in re.finditer(RESOURCE, text, re.I):
            left, right = min(action.start(), resource.start()), max(action.end(), resource.end())
            if right-left > 180 or re.search(BOUNDARY, text[left:right], re.I):
                continue
            if action is requirement:
                if not re.search(r"\bto\s+(?:buy|purchase|access|rent)\b", text[action.end():resource.start()], re.I):
                    continue
            else:
                preceding = text[max(0, resource.start()-70):resource.start()]
                following = text[resource.end():resource.end()+30]
                if not (re.search(r"\baccess\s+(?:to\s+)?(?:(?:advanced|remote|AI)\s+){0,3}$", preceding, re.I)
                        or re.match(r"\s+(?:remote\s+)?access\b", following, re.I)):
                    continue
            before = text[max(0, action.start()-60):action.start()]
            if re.search(r"\b(?:designed to|aims? to|ability to|used to)\s*$", before, re.I):
                continue
            planned = bool(re.search(r"\b(?:will|plans? to|proposes? to)\s*$", before, re.I))
            return {"version": VERSION, "event_type": "ACCESS_RESTRICTION",
                    "phase": "FORWARD_LOOKING" if planned else "SOURCE_REPORTED_REQUIREMENT",
                    "text": text, "action_span": span(text, action.start(), action.end()),
                    "object_span": span(text, resource.start(), resource.end()),
                    "financial_impact": "UNKNOWN", "identity_verified": False,
                    "legal_status_verified": False, "company_order_verified": False,
                    "offset_basis": "RELATIVE_TO_SOURCE_WINDOW_TEXT"}
    return None


def matches(binding, fields):
    rule = binding.access_constraint
    for field, text in fields.items():
        for sentence in sentences(text):
            value = sentence.group()
            if any(re.search(r"\b"+re.escape(t)+r"\b", value, re.I) for t in binding.exclude_terms):
                continue
            event = classify(value)
            if not event:
                continue
            names = [m for n in rule.company_terms for m in re.finditer(r"(?<!\w)"+re.escape(n)+r"(?!\w)", value, re.I)]
            # Name must introduce the company's product/buyer/seller scope in
            # this clause. Analyst commentary cannot donate a company identity.
            company = next((m for m in names if re.match(
                r"(?:['’]s)?\s+(?:chip|GPU|compute|AI|buyers?|sellers?|customers?)\b", value[m.end():], re.I)
                and not re.search(BOUNDARY, value[min(m.start(), event['action_span']['start']):
                                                max(m.end(), event['object_span']['end'])], re.I)), None)
            if company is None:
                continue
            event['company_span'] = span(value, company.start(), company.end())
            return [{**s, "field": field, "start": s['start']+sentence.start(), "end": s['end']+sentence.start(),
                     "group": "access_constraint", "activity_assertion": event,
                     "relevance_role": "ACCESS_CONSTRAINT_CONTEXT", "news_party_verified": False}
                    for s in (event['company_span'], event['action_span'], event['object_span'])]
    return []
