"""Source-local supply access, investment purpose and customer contracts.

Consumes an already sourced narrative match; creates no counterpart, quantity,
contract terms, operational outcome or financial estimate.
"""

import re

from engine.operating_developments import span

RESOURCE = r"\b(?:materials?|minerals?|components?|chemicals?|wafers?|substrates?|inputs?)\b"
PROCESS = r"\b(?:processing|purification|manufacturing|production|refining|capacity)\b"
CONTRACT = r"\b(?:(?:strategic|long[ -]term|multi[ -]year)\s+)*(?:customer|supply|procurement|offtake|take[ -]or[ -]pay)\s+(?:agreements?|contracts?)\b"
BOUNDARY = r"[,;!?\n]|\b(?:but|whereas|while|and)\b"


def assess(text):
    definitions = [
        ("SUPPLY_ACCESS", r"\b(?:expand(?:s|ed)?|secur(?:e|es|ed)|improv(?:e|es|ed))\s+(?:(?:reliable|domestic|long-term)\s+){0,2}(?:access|availability|supply)\s+(?:to|of)\b", RESOURCE),
        ("INPUT_FINANCING_PURPOSE", r"\b(?:invest(?:s|ed)?\s+in|fund(?:s|ed)?|financ(?:e|es|ed))\b", RESOURCE),
        ("CUSTOMER_AGREEMENT", r"\b(?:complet(?:e|es|ed)|sign(?:s|ed)?|enter(?:s|ed)?\s+into|announc(?:e|es|ed)|extend(?:s|ed)?|renew(?:s|ed)?)\b", CONTRACT),
    ]
    for event, pattern, objects in definitions:
        for action in re.finditer(pattern, text, re.I):
            # Never turn an infinitive purpose/capability into an achieved result.
            before = text[max(0, action.start() - 100):action.start()]
            if re.search(r"\b(?:can|could|might|would|designed to|helps? to|enables?\s+\w+\s+to)\s*$", before, re.I):
                continue
            planned = bool(re.search(r"\b(?:will|plans? to|expects? to|to)\s*$", before, re.I))
            end = min(len(text), action.end() + 180)
            boundary = re.search(BOUNDARY, text[action.end():end], re.I)
            if boundary:
                end = action.end() + boundary.start()
            tail = text[action.end():end]
            if re.search(r"\b(?:shares?|stocks?|scholarships?|lawsuits?|litigation|real estate)\b", tail, re.I):
                continue
            obj = re.search(objects, tail, re.I)
            if not obj or re.search(r"\b(?:for|by|about|which|that|said|says)\b", tail[:obj.start()], re.I):
                continue
            if event == "INPUT_FINANCING_PURPOSE" and not re.search(PROCESS, tail, re.I):
                continue
            return {"event_type": event, "phase": "FORWARD_LOOKING" if planned else
                    "SOURCE_REPORTED_AGREEMENT" if event == "CUSTOMER_AGREEMENT" else
                    "SOURCE_REPORTED_ALLOCATION" if event == "INPUT_FINANCING_PURPOSE" else "SOURCE_REPORTED_CHANGE",
                    "action_span": span(text, action.start(), action.end()),
                    "object_span": span(text, action.end() + obj.start(), action.end() + obj.end()),
                    "driver_direction": "UNKNOWN", "operational_outcome": "UNKNOWN",
                    "contract_terms": "NOT_INFERRED"}
    return None
