"""Bounded market applicability, not a general semantic classifier.

Domains describe source wording. Only a reviewed profile binding decides whether
that wording can support its market path. Unknown domains retain legacy behavior.
"""

import re

VERSION = "news-applicability-v1"
DOMAINS = {
    "COMPONENT_MARKET": r"\b(?:memory|flash|DRAM|NAND|HBM|semiconductors?|chips?|processors?|CPUs?|GPUs?|TPUs?)\b",
    "APPLICATION_SOFTWARE": r"\b(?:software|applications?|libraries|library|simulation|simulations|world models|apps?)\b",
    "INFRASTRUCTURE_DEMAND": r"\b(?:data[ -]?cent(?:er|re)s?|servers?|GPU clusters?|AI infrastructure|compute capacity|AI factory|AI factories)\b",
}
ASSET = r"(?:GPUs?|servers?|clusters?|data[ -]?cent(?:er|re)s?)"
QUALIFIERS = r"(?:(?:\d[\d,]*|new|additional|more|the|a|an|AI|GPU)\s+){0,4}"
BRIDGES = [
    r"\bdeploy(?:s|ed|ing)?\s+(?:up to\s+)?\d+(?:\.\d+)?\s+(?:giga|mega)watts?\s+of\s+(?:[\w™-]+\s+){0,6}(?:GPUs?|servers?|compute capacity)\b",
    r"\b(?:deploy(?:s|ed|ing)?|install(?:s|ed|ing)?|order(?:s|ed|ing)?|purchas(?:e|es|ed|ing)|build(?:s|ing)?|expand(?:s|ed|ing)?)\s+" + QUALIFIERS + ASSET + r"\b",
    r"\b" + ASSET + r"\s+(?:(?:are|were|will be)\s+)?(?:deployed|installed|ordered|purchased)\b",
    r"\bdemand for (?:additional |more )?(?:GPU|server|AI compute|cloud computing|data center) capacity\b",
    r"\b(?:server|data center|AI compute) (?:capacity|demand|orders)\s+(?:has |have |is |are )?(?:ris(?:e|es|ing)|increas(?:e|es|ed|ing)|expand(?:s|ed|ing))\b",
    r"\bservers?(?:\s+OEMs?)?\s+(?:(?:prices?|costs?)\s+(?:ris(?:e|es|ing)|increas(?:e|es|ed|ing))|(?:hiking|raising)\s+prices)\b",
]
NONASSERTION = re.compile(
    r"\b(?:no|not|never|could|might|may|would|can|if|hypothetical|rumou?rs?|"
    r"enables?|helps?|designed to|cancelled|canceled)\b", re.I
)


def evidence(text, field):
    return [{"domain": domain, "field": field, "start": m.start(), "end": m.end(),
             "text": m.group()} for domain, pattern in DOMAINS.items()
            for m in re.finditer(pattern, text, re.I)]


def assess(target, title, sentence):
    """A component/app story needs a same-sentence infrastructure assertion.

    Headline context can tighten a gate, never donate a deployment assertion to
    another sentence. Mere capacity of memory is not compute deployment capacity.
    """
    observed = evidence(title, "context_title") + evidence(sentence, "window")
    domains = {r["domain"] for r in observed}
    cross_domain = target == "INFRASTRUCTURE_DEMAND" and bool(
        domains & {"COMPONENT_MARKET", "APPLICATION_SOFTWARE"}
    )
    bridge = None if NONASSERTION.search(sentence) else next(
        (m for pattern in BRIDGES if (m := re.search(pattern, sentence, re.I))), None
    )
    allowed = not cross_domain or bridge is not None
    return {"version": VERSION, "target": target,
            "observed_domains": sorted(domains) or ["UNKNOWN"],
            "allowed": allowed, "basis": "EXPLICIT_INFRASTRUCTURE_ASSERTION"
            if cross_domain and bridge else "CROSS_DOMAIN_WITHOUT_ASSERTION"
            if cross_domain else "NO_CROSS_DOMAIN_RESTRICTION",
            "evidence": observed, "bridge": {"start": bridge.start(), "end": bridge.end(),
                                               "text": bridge.group()} if bridge else None,
            "financial_impact": "UNKNOWN"}
