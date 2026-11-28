"""Capital committed to a stated deployment asset, on an exact sourced route.

No supplier inference, disbursement claim, capacity completion or amount extraction.
"""

import re

from engine.source_references import data_center
from engine.source_sentences import sentences

VERSION = "project-finance-v1"
MARKET = r"\b(?:data[ -]?cent(?:er|re)s?|AI infrastructure)\b"
CAPITAL = r"\b(?:capital|funds|funding|financing|loans?|credit)\b"
ACTION = r"\b(?:secures?|secured|obtains?|obtained|raises?|raised|commits?|committed|provides?|provided|arranges?|arranged)\b"
PURPOSE = r"\b(?:for|to build|to construct|to develop|to expand)\b"
BOUNDARY = r"[,;!?]|\b(?:and|but|while|whereas)\b"


def supported(evidence):
    return any(re.search(CAPITAL, e.quote, re.I) and re.search(MARKET, e.quote, re.I) for e in evidence)


def span(text, start, end):
    return {"text": text[start:end], "start": start, "end": end}


def classify(text, reference=None):
    if (len(text) > 1200 or '?' in text or re.search(
            r"\b(?:not|never|denied|may|might|could|would|if|unless|rumou?r|lawsuit|conference|software)\b", text, re.I)):
        return None
    # A named source actor, not a profile identity. Attribution and predicates
    # must be local; another clause cannot donate the financing purpose.
    actor = re.match(r"\s*(?P<actor>[A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,4})\s+(?:(?:will|plans to)\s+)?", text)
    if not actor:
        return None
    action = re.match(ACTION, text[actor.end():], re.I)
    if not action:
        return None
    action_start, action_end = actor.end()+action.start(), actor.end()+action.end()
    capital = re.search(CAPITAL, text[action_end:action_end+70], re.I)
    if not capital or re.search(BOUNDARY, text[action_end:action_end+capital.end()], re.I):
        return None
    # Only a quantity/denomination may separate the financing verb and capital.
    gap=text[action_end:action_end+capital.start()]
    if not re.fullmatch(r"\s*(?:(?:a|an)\s+|(?:\$|USD\s*)?\d[\d,.]*\s*(?:million|billion)?\s*(?:in\s+)?)?", gap, re.I):
        return None
    cap_start, cap_end=action_end+capital.start(),action_end+capital.end()
    purpose = re.match(r"\s*"+PURPOSE, text[cap_end:], re.I)
    if not purpose:
        return None
    purpose_end=cap_end+purpose.end()
    asset=re.search(MARKET, text[purpose_end:purpose_end+110], re.I)
    reference_used=False
    if asset:
        asset_start,asset_end=purpose_end+asset.start(),purpose_end+asset.end()
    elif reference:
        base=reference['window_span']['start']
        asset_start=reference['reference_span']['start']-base
        asset_end=reference['reference_span']['end']-base
        reference_used=True
    else:
        return None
    if not purpose_end <= asset_start <= purpose_end+110:
        return None
    if not re.fullmatch(r"\s*(?:(?:a|an|the|new|its|this|that)\s+)?", text[purpose_end:asset_start], re.I):
        return None
    # Data-center software/cooling funds are not facility-project financing.
    if not re.match(r"\s*(?:$|[,.]|\b(?:in|near|outside|with|expansion|construction|development)\b)", text[asset_end:], re.I):
        return None
    return {"version":VERSION,"event_type":"PROJECT_FINANCE_CONTEXT","text":text,
        "actor_span":span(text,actor.start('actor'),actor.end('actor')),
        "actor_role":"CAPITAL_PROVIDER" if re.match(r"(?:commit|provide)",action.group(),re.I) else
                     "FINANCING_ARRANGER" if re.match(r"arrange",action.group(),re.I) else "CAPITAL_RECIPIENT",
        "action_span":span(text,action_start,action_end),"capital_span":span(text,cap_start,cap_end),
        "object_span":span(text,asset_start,asset_end),
        **({'source_reference':reference} if reference_used else {}),
        "phase":"FORWARD_LOOKING" if re.search(r"\b(?:will|plans to)\b",text[:action_start],re.I) else "SOURCE_REPORTED_FINANCING",
        "identity_verified":False,"supplier_relationship_inferred":False,
        "capital_disbursed":"UNKNOWN","operating_capacity":"UNKNOWN","amount":"NOT_EXTRACTED",
        "financial_impact":"UNKNOWN","offset_basis":"RELATIVE_TO_SOURCE_WINDOW_TEXT"}


def matches(binding, fields, *, payload=None):
    for field,text in fields.items():
        for sentence in sentences(text):
            value=sentence.group()
            if any(re.search(r"(?<!\w)"+re.escape(t)+r"(?!\w)",value,re.I) for t in binding.exclude_terms):
                continue
            reference=data_center(payload or fields,field,text,sentence.start(),subject_only=False)
            event=classify(value,reference)
            if event:
                event['relationship_id']=binding.project_finance.relationship_id
                return [{**event[key],"start":sentence.start()+event[key]['start'],
                    "end":sentence.start()+event[key]['end'],"field":field,"group":"project_finance",
                    "project_finance":event,"context_only":True,"news_party_verified":False,
                    "relevance_role":"PROJECT_FINANCE_CONTEXT"}
                    for key in ['actor_span','action_span','capital_span','object_span']]
    return []
