"""Bounded activity assertions, not company orders or financial impact estimates.

Vocabulary describes reusable event groups. Applicability lives in reviewed profile
bindings; no issuer ticker, article title or inferred customer is a routing rule.
"""

import re

from engine.source_sentences import sentences

VERSION = "activity-assertions-v1"
MARKETS = {
    "DATA_CENTER": r"\b(?:data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?)\b",
    "AI_COMPUTE": r"\b(?:GPUs?|AI (?:supercomputers?|compute|infrastructure)|accelerated computing)\b",
}
ACTIONS = {
    "FACILITY_PROJECT": r"\b(?:announces?|plans?|proposes?|builds?|building|construction|develop(?:s|ment|ing)|invest(?:s|ing)|opens?|opening)\b",
    "PROJECT_FINANCING": r"\b(?:seeks? (?:an? )?investment partner|seeking (?:an? )?investment partner|secur(?:es|ed) (?:funding|financing)|commits?|invest(?:s|ment|ing))\b",
    "COMPUTE_DEPLOYMENT": r"\b(?:deploy(?:s|ed|ing|ment)?|install(?:s|ed|ing)|commission(?:s|ed|ing)|launch(?:es|ed)?)\b",
    "PRODUCT_INTEGRATION": r"\b(?:integrat(?:e|es|ed|ion|ing)|complement(?:s|ing)?|incorporat(?:e|es|ed|ing))\b",
}
DENIAL = re.compile(
    r"\b(?:no|not|never|without|denies?|denied|rumou?rs?|cancel(?:s|led|ed|lation)?|"
    r"abandon(?:s|ed)?|hypothetical|could|might|may|if)\b", re.I
)
# Only explicit technology ownership is a supplier assertion. A party after
# "deployed by" can be an operator and is deliberately not interpreted as a vendor.
VENDOR = re.compile(
    r"\b(?:powered by|built (?:with|using)|based on)\s+"
    r"(?P<name>[A-Z][\w.-]*(?:\s+(?:and\s+)?[A-Z][\w.-]*){0,4})"
    r"\s+(?:technology|GPUs?|processors?|chips?|hardware|accelerators?)\b"
)


def literal(term, text):
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)


def activity_matches(binding, fields, *, bundle=None, at=None):
    rule = binding.activity_rule
    if rule is None:
        return []
    if rule.version == "activity-assertions-v2":
        from engine.market_developments import matches

        return matches(binding, fields, bundle=bundle, at=at)
    for field, text in fields.items():
        for window in sentences(text):
            value = window.group()
            if len(value) > 1200 or DENIAL.search(value):
                continue
            if any(literal(t, value) for t in binding.exclude_terms):
                continue
            vendors = list(VENDOR.finditer(value))
            if rule.vendor_names and any(
                not any(literal(name, vendor["name"]) for name in rule.vendor_names)
                for vendor in vendors
            ):
                continue
            if rule.market == "NAMED_PRODUCT":
                market = next((m for t in rule.product_terms if (m := literal(t, value))), None)
            else:
                market = re.search(MARKETS[rule.market], value, re.I)
            if market is None:
                continue
            for kind in rule.event_types:
                action = re.search(ACTIONS[kind], value, re.I)
                if action is None:
                    continue
                if kind in {"FACILITY_PROJECT", "PROJECT_FINANCING"} and re.search(
                    r"\b(?:rules|regulations|legislation|bill|policies)\b", value, re.I
                ):
                    # A proposed rule is not a proposed facility. Existing policy
                    # bindings can still route this sentence independently.
                    continue
                # Facility projects need a project context, not "data center demand grows".
                if kind == "FACILITY_PROJECT" and not re.search(
                    r"(?<![A-Za-z])(?:MW|GW)\b|\b(?:facility|facilities|campus|project|site|construction|development|first|new)\b", value, re.I
                ):
                    continue
                phase = "SOURCE_REPORTED_ACTIVITY"
                if re.search(r"\b(?:seek|seeks|seeking)\b", value, re.I):
                    phase = "SEEKING_FINANCING"
                elif re.search(r"\b(?:will|plan|plans|planned|proposed|proposes|agreement|subject to)\b|\bto\s+(?:deploy|build|install|integrate|open)\b", value, re.I):
                    phase = "FORWARD_LOOKING"
                elif re.search(r"\b(?:deployed|installed|opened|commissioned)\b", value, re.I):
                    phase = "SOURCE_REPORTED_DEPLOYMENT"
                assertion = {
                    "version": VERSION, "event_type": kind, "market": rule.market,
                    "phase": phase, "vendor_scope": "EXPLICIT_TECHNOLOGY" if vendors else "UNSPECIFIED",
                    "company_order_verified": False, "financial_impact": "UNKNOWN",
                }
                return [
                    {"group": group, "field": field,
                     "start": window.start() + hit.start(), "end": window.start() + hit.end(),
                     "text": hit.group(), "scope_basis": "PROFILE_BOUND_ACTIVITY_ASSERTION",
                     "activity_assertion": assertion}
                    for group, hit in (("activity_market", market), ("activity_action", action))
                ]
    return []
