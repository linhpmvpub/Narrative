"""Opt-in resource/operating-market context, never company incident attribution."""

import re

from engine.source_sentences import sentences

VERSION = "readiness-context-v1"
RESOURCES = {
    "POWER": r"\b(?:power|electricity|electrical|grid)\b",
    "WATER": r"\bwater\b",
    "CONSTRUCTION": r"\bconstruction\b",
}
MARKETS = {
    "CUSTOMER_DEPLOYMENT": r"\bdata[ -]?cent(?:er|re)s?\b",
    "MANUFACTURING": r"\b(?:manufacturing|production|fabs?)\b",
}
OPERATING = r"\b(?:availability|capacity|constraints?|shortages?|outages?|disturbances?|disrupt(?:s|ed|ions?)?|strain|stranded|recover|delays?|delayed|paused|halted|schedule|buildout)\b"
BOUNDARY = r"[;!?]|\b(?:and|but|whereas|while)\b"


def resource_condition(res, action, value):
    """Bind the condition to the resource, not another component's capacity.

    A mere mention of low-power memory and memory capacity is not utility
    availability. Only bounded resource-condition noun phrases qualify here.
    """
    if res.end() <= action.start():
        gap = value[res.end():action.start()]
        return bool(re.fullmatch(r"[ -]*(?:(?:supply|generation|delivery|grid|service|construction)[ -]+)?", gap, re.I))
    if action.end() <= res.start():
        gap = value[action.end():res.start()]
        return bool(re.fullmatch(r"[ -]*(?:(?:of|in|to)[ -]+)?(?:data[ -]?cent(?:er|re)[ -]+)?(?:electrical[ -]+)?", gap, re.I))
    return False


def supported(rule, evidence):
    """Require each declared resource and operating scope in a supplied quote."""
    return all(any(re.search(RESOURCES[resource], e.quote, re.I)
                   and re.search(MARKETS[rule.scope], e.quote, re.I) for e in evidence)
               for resource in rule.resources)


def matches(binding, fields):
    rule = binding.readiness_context
    for field, text in fields.items():
        for sentence in sentences(text):
            value = sentence.group()
            if len(value) > 1200 or any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", value, re.I)
                                       for t in binding.exclude_terms):
                continue
            # General industrial utility explainers are context, but a factory in
            # an unrelated sector must not imply semiconductor supply exposure.
            for resource in rule.resources:
                for res in re.finditer(RESOURCES[resource], value, re.I):
                    for market in re.finditer(MARKETS[rule.scope], value, re.I):
                        if rule.scope == "MANUFACTURING" and not (
                            re.search(r"\b(?:semiconductor|chip|memory)\s+(?:device\s+)?$", value[:market.start()], re.I)
                            or re.search(r"\b(?:how|why)\b[^;.!?]*\bindustrial\s+(?:power|water|electricity)\b", value, re.I)
                        ):
                            continue
                        for action in re.finditer(OPERATING, value, re.I):
                            if not resource_condition(res, action, value):
                                continue
                            hits = [res, market, action]
                            left, right = min(h.start() for h in hits), max(h.end() for h in hits)
                            window = value[left:right]
                            if right-left > 220 or re.search(BOUNDARY, window, re.I):
                                continue
                            # Denial changes applicability, even though this path
                            # never claims a realized financial effect.
                            if re.search(r"\b(?:not|never|denied|no)\b", value, re.I):
                                continue
                            trace = {"version": VERSION, "scope": rule.scope, "resource": resource,
                                     "relationship_id": rule.relationship_id, "text": value,
                                     "company_incident_verified": False, "financial_impact": "UNKNOWN"}
                            return [{"field": field, "start": h.start()+sentence.start(),
                                     "end": h.end()+sentence.start(), "text": h.group(), "group": group,
                                     "readiness_context": trace, "context_only": True,
                                     "relevance_role": "OPERATING_READINESS_CONTEXT", "news_party_verified": False}
                                    for h, group in zip(hits, ("resource", "market", "operating_context"), strict=True)]
    return []
