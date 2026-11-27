"""Opt-in source-window scope checks, not inferred customers or impact estimates."""

import re

VERSION = "routing-guards-v1"
INFRA_ASSET = r"\b(?:data[ -]?cent(?:er|re)s?|server farms?|GPU clusters?|compute capacity|AI supercomputers?)\b|\b\d+(?:\.\d+)?\s*(?:MW|GW|megawatts?|gigawatts?)\b"
OTHER_MARKET = r"\b(?:automotive|vehicles?|cars?|smartphones?|handsets?|mobile phones?)\b"
SERVER_MARKET = r"\b(?:servers?|data[ -]?cent(?:er|re)s?|enterprise SSDs?|hyperscalers?)\b"
CONSTRAINT = r"\b(?:shortages?|bottlenecks?|constraints?|scarcity|disruptions?|outages?|limited supply|supply limits?|supply crunch|power limits?)\b|\b(?:prices?|costs?)\s+(?:ris(?:e|es|ing)|increas(?:e|es|ed|ing))\b|\b(?:higher|rising|increased)\s+(?:\w+\s+){0,2}(?:prices?|costs?)\b"
NEGATION = r"\b(?:no|not|never|without|denied|hypothetical|rumou?rs?|could|might)\b"


def assess(guards, title, window):
    """Titles can constrain product scope, never donate a positive assertion."""
    checks = []
    for guard in guards:
        evidence = None
        if guard == "INFRASTRUCTURE_FINANCING":
            evidence = re.search(INFRA_ASSET, window, re.I)
            allowed = bool(evidence) and not re.search(NEGATION, window, re.I)
        elif guard == "SERVER_COMPONENT_MARKET":
            foreign = re.search(OTHER_MARKET, title + " " + window, re.I)
            evidence = re.search(SERVER_MARKET, window, re.I)
            allowed = not foreign or bool(evidence)
        elif guard == "SECTOR_CONSTRAINT":
            evidence = re.search(CONSTRAINT, window, re.I)
            allowed = bool(evidence) and not re.search(NEGATION, window, re.I)
        else:
            raise ValueError("Unknown routing guard")
        checks.append({"guard": guard, "allowed": bool(allowed),
                       "evidence": {"start": evidence.start(), "end": evidence.end(),
                                    "text": evidence.group()} if evidence else None})
    return {"version": VERSION, "allowed": all(c["allowed"] for c in checks),
            "checks": checks, "window_text": window,
            "offset_basis": "RELATIVE_TO_WINDOW_TEXT", "financial_impact": "UNKNOWN"}
