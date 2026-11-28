"""Source-local project participants and technology ownership, not orders.

Names and competition edges come from a reviewed profile. A generic operator is
not forced to be a known customer; explicit other-vendor projects cannot donate
demand to every supplier. No cross-sentence, headline or pronoun inference.
"""

import re

from engine.relationship_roles import roles
from engine.source_sentences import LEGAL_SUFFIX

VERSION = "infrastructure-scope-v2"
NAME = r"[A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,3}"
AUX = r"(?:(?:has|have|had|is|are|was|were|will|also|now|jointly|recently|plans? to)\s+)*"
ACTION = r"(?:plans?|planned|propos(?:es?|ed)|builds?|building|construct(?:s|ed|ing)?|opens?|opened|deploy(?:s|ed|ing)?|launch(?:es|ed)?|expand(?:s|ed|ing)?|install(?:s|ed|ing)?)\b"
TECHNOLOGY = r"(?:technology|GPUs?|CPUs?|processors?|chips?|hardware|accelerators?|servers?)"


def hit(text, start, end):
    return {"start": start, "end": end, "text": text[start:end]}


def literal(name, text):
    return re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I)


def participants(names, text, asset):
    """Only bounded subjects, possessive technology or explicit project work."""
    result: list[dict] = []
    for name in sorted(names, key=len, reverse=True):
        for m in literal(name, text):
            before, after = text[:m.start()], text[m.end():]
            role = None
            # A quoted name, customer of, analyst about, or operator after 'by'
            # is not automatically a technology supplier.
            lead = bool(re.fullmatch(r"\s*(?:" + NAME + r"\s+(?:and|&)\s+)?", before))
            if re.search(r"\b(?:and|but|whereas|while)\s*$", before, re.I) and re.search(ACTION, before, re.I):
                lead = True  # An independent coordinated clause has its own subject.
            suffix = re.sub(r"^\s*,?\s*" + LEGAL_SUFFIX, "", after, flags=re.I)
            joint = re.match(r"\s+(?:and|&)\s+" + NAME + r"\s+", suffix)
            if joint:
                suffix = suffix[joint.end():]
            if lead and m.end() < asset["start"]:
                if verb := re.match(r"\s*" + AUX + ACTION, suffix, re.I):
                    bridge = suffix[verb.end():len(suffix) - (len(text) - asset['start'])]
                    if not re.search(r"[,;!?]|\b(?:and|but|while|whereas)\b", bridge, re.I):
                        role = "PROJECT_ACTOR"
                elif re.match(r"\s*" + AUX + r"(?:working|collaborating|partnering)\s+with\b", suffix, re.I):
                    bridge = text[m.end():asset["start"]]
                    if len(bridge) <= 300 and re.search(r"\bon\b", bridge, re.I) and not re.search(r"[,;!?]|\b(?:but|while|whereas)\b", bridge, re.I):
                        role = "PROJECT_PARTICIPANT"
            if re.match(r"(?:['’]s)?\s+" + TECHNOLOGY + r"\b", after, re.I):
                # Restrict a technology mention to the asset's same clause.
                bridge = text[min(m.start(), asset['start']):max(m.end(), asset['end'])]
                linked = re.search(r"\b(?:powered by|built with|built using|based on|using|with)\s*$", before, re.I)
                embedded = asset['start'] >= m.end() and re.fullmatch(r"(?:['’]s)?\s+", text[m.end():asset['start']])
                if (linked or embedded) and len(bridge) <= 300 and not re.search(r"[,;!?]|\b(?:but|while|whereas)\b", bridge, re.I):
                    role = "TECHNOLOGY_REFERENCE"
            if role and not any(x['span']['start'] <= m.start() < x['span']['end'] for x in result):
                result.append({"role": role, "span": hit(text, m.start(), m.end())})
    return result


def assess(scope, development, bundle, at):
    base = {"version": VERSION, "allowed": False, "reason": "PROFILE_SCOPE_UNAVAILABLE",
            "actor_identity": "UNKNOWN", "company_order_verified": False,
            "financial_impact": "UNKNOWN", "offset_basis": "RELATIVE_TO_SOURCE_WINDOW_TEXT"}
    if bundle is None or at is None:
        return base
    edges = {r.id: r for r in bundle.relationships}
    for peer in scope.competitors:
        r = edges.get(peer.relationship_id)
        if (r is None or r.status != "SOURCE_BACKED" or r.type != "COMPETES_WITH"
                or r.known_at > at or r.valid_from > at or (r.valid_until and at >= r.valid_until)):
            return {**base, "reason": "COMPETITION_SCOPE_NOT_CURRENT"}
    text, asset = development['text'], development['object_span']
    own = participants(scope.own_names, text, asset)
    peers = [{**p, "relationship_id": c.relationship_id}
             for c in scope.competitors for p in participants(c.names, text, asset)]
    # Uncatalogued vendors are not assumed to be the profile company. This is
    # a literal source claim; it does not add a competitor node or identity.
    explicit = []
    for m in re.finditer(r"\b(?i:powered by|built with|built using|based on)\s+(?P<vendor>" + NAME + r")\s+(?i:" + TECHNOLOGY + r")\b", text):
        bridge = text[min(asset['start'], m.start()):max(asset['end'], m.end())]
        if len(bridge) <= 350 and not re.search(r"[,;!?]|\b(?:but|while|whereas)\b", bridge, re.I):
            explicit.append(hit(text, m.start('vendor'), m.end('vendor')))
    unsupported = [v for v in explicit if not any(list(literal(n, v['text'])) for n in scope.own_names)]
    own_technology = any(p['role'] == 'TECHNOLOGY_REFERENCE' for p in own)
    # Competition is product scoped, not an exclusive company identity. Merely
    # operating a facility cannot establish its technology vendor or customer.
    # A named third-party collaboration stays scoped to its explicit participants;
    # generic sector context must not invent the profile company's participation.
    vendor_scoped = [p for p in peers if p['role'] != 'PROJECT_ACTOR']
    allowed = (bool(own) and (not unsupported or own_technology)) or not (vendor_scoped or unsupported)
    graph_roles = {node: roles(bundle, node, at) for c in scope.competitors
                   for node in (edges[c.relationship_id].from_id, edges[c.relationship_id].to_id)}
    return {**base, 'allowed': allowed,
            'reason': 'OTHER_VENDOR_PROJECT_SCOPE' if not allowed else
                      'OWN_PARTICIPATION_CONDITIONAL' if own else 'GENERIC_MARKET_NOT_VENDOR_PROOF',
            'own_participants': own, 'other_participants': peers, 'explicit_technology_vendors': explicit,
            'graph_roles': graph_roles, 'roles_are_nonexclusive': True,
            'customer_relationship_inferred': False, 'supplier_relationship_inferred': False,
            'operator_is_not_technology_vendor': True,
            'asset_span': asset, 'text': text}
