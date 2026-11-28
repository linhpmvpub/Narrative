"""Explicit backing of an operating counterparty, not disbursed funds or orders."""

import re

from engine.operating_developments import span

ACTION = r"\b(?:backs?|backed|funds?|funded|finances?|financed|invests? in|invested in)\b"
PARTY = r"\s+(?:(?:a|an|the|new|local)\s+){0,3}(?P<party>startup|start-up|company|supplier|manufacturer|developer)\b"
PURPOSE = r"\b(?:developing|building|manufacturing|producing|to develop|to build|to manufacture|to produce)\b"
ASSET = r"\b(?:cooling(?: systems?)?|memory(?: chips?)?|semiconductors?|servers?|AI infrastructure|data centers?|data centres?|power generation|packaging capacity)\b"
BOUNDARY = r"[,;!?]|\b(?:but|while|whereas|and|about|against|discussing)\b"


def assess(text):
    if len(text) > 1200 or re.search(r"\b(?:not|never|denied|may|might|could|would|if|unless|rumou?r)\b", text, re.I) or '?' in text:
        return None
    for action in re.finditer(ACTION, text, re.I):
        before = text[:action.start()]
        if not before.strip() or re.search(r"\b(?:designed to|used to|helps? to|ability to|aims? to)\s*$", before, re.I):
            continue
        planned = bool(re.search(r"\b(?:will|plans? to|expects? to)\s*$", before, re.I))
        if re.search(r"\bto\s*$", before, re.I) and not planned:
            continue
        party = re.match(PARTY, text[action.end():], re.I)
        if not party:
            continue
        end = min(len(text), action.end()+240)
        stop = re.search(BOUNDARY, text[action.end():end], re.I)
        if stop:
            end = action.end()+stop.start()
        purpose = re.search(PURPOSE, text[action.end()+party.end():end], re.I)
        if not purpose:
            continue
        purpose_start = action.end()+party.end()+purpose.start()
        purpose_end = action.end()+party.end()+purpose.end()
        asset = re.search(ASSET, text[purpose_end:end], re.I)
        if not asset:
            continue
        bridge = text[purpose_end:purpose_end+asset.start()]
        if re.search(r"\b(?:software|applications?|services?|marketing|tools|guide|training|for|to|with|that|which)\b", bridge, re.I):
            continue
        return {"version": "capital-backing-v1", "event_type": "CAPITAL_BACKING",
                "phase": "FORWARD_LOOKING" if planned else "SOURCE_REPORTED_BACKING",
                "action_span": span(text, action.start(), action.end()),
                "counterparty_span": span(text, action.end()+party.start('party'), action.end()+party.end('party')),
                "purpose_action_span": span(text, purpose_start, purpose_end),
                "object_span": span(text, purpose_end+asset.start(), purpose_end+asset.end()),
                "driver_direction": "UNKNOWN", "capital_disbursed": "UNKNOWN",
                "operational_outcome": "UNKNOWN", "amount": "NOT_EXTRACTED",
                "ownership_or_customer_relationship": "NOT_INFERRED"}
    return None
