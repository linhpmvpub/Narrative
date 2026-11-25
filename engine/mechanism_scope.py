"""Source-grounded per-mechanism context scope; never economic transmission approval."""

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from engine.ingestion.contracts import digest

FACETS = {"legal_entity", "product", "facility", "geography", "period"}
REQUIRED = {
    "supply_disruption": FACETS,
    "input_price": {"legal_entity", "product", "geography", "period"},
    "capacity": {"legal_entity", "product", "geography", "period"},
    "demand": {"legal_entity", "product", "period"},
    "technology": {"legal_entity", "product", "period"},
    "financing": {"legal_entity", "period"},
    "policy": {"legal_entity", "product", "geography", "period"},
}
DEFAULT = Path(__file__).resolve().parent.parent / "config/mechanism-scope.json"


class NotApplicable(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    event_quote: str = Field(min_length=10, max_length=8000)
    exposure_quote: str = Field(min_length=10, max_length=8000)
    rationale: str = Field(min_length=30, max_length=2000)


class ContextScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mechanism_id: str
    not_applicable: dict[str, NotApplicable] = Field(default_factory=dict)


def load(path=DEFAULT):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        data.get("schema") != "mechanism-scope-v1"
        or data.get("version") != 1
        or data.get("level") != "RELATED_CONTEXT_ONLY"
        or data.get("delivery") != "disabled"
        or data.get("conditional_policy") != "MATCH_OR_EXPLICIT_SOURCE_BACKED_NOT_APPLICABLE"
        or data.get("unknown_policy") != "HOLD_CONTEXT"
        or data.get("impact_gate") != "UNCHANGED_STRICT_R05"
        or data.get("status") != "ENGINEERING_POLICY_NOT_EMPIRICALLY_VALIDATED"
        or set(data.get("groups", {})) != set(REQUIRED)
    ):
        raise ValueError("Unsupported mechanism scope contract")
    for name, required in REQUIRED.items():
        group = data["groups"][name]
        if (
            set(group) != {"required", "conditional"}
            or set(group["required"]) != required
            or set(group["conditional"]) != FACETS - required
            or len(group["required"]) + len(group["conditional"]) != len(FACETS)
        ):
            raise ValueError("Unsupported mechanism facet requirements")
    return data


def contains(text, quote):
    return bool(re.search(r"(?<!\w)" + re.escape(quote) + r"(?!\w)", text))


def assess(contract, facets, event_quote, exposure_quote, mechanism_id):
    policy = load()
    if contract.policy_sha256 != digest(policy) or contract.mechanism_id != mechanism_id:
        raise ValueError("Context scope policy/mechanism changed; new review required")
    group = policy["groups"][mechanism_id]
    na = set(contract.not_applicable)
    matched = set(facets)
    if (
        not set(group["required"]) <= matched
        or not na <= set(group["conditional"])
        or matched & na
        or matched | na != FACETS
    ):
        raise ValueError(
            "Every scope facet requires a match or permitted evidenced not-applicable decision"
        )
    for evidence in contract.not_applicable.values():
        if not contains(event_quote, evidence.event_quote) or not contains(
            exposure_quote, evidence.exposure_quote
        ):
            raise ValueError("Not-applicable justification missing from pinned source quotes")
    return {
        "policy_sha256": digest(policy),
        "mechanism_id": mechanism_id,
        "level": "RELATED_CONTEXT_ONLY",
        "facets": {
            f: "REVIEWED_NOT_APPLICABLE" if f in na else "LITERAL_MATCH" for f in sorted(FACETS)
        },
        "not_applicable": {
            k: v.model_dump(mode="json") for k, v in contract.not_applicable.items()
        },
        "basis": "REVIEWER_INTERPRETATION_NOT_AUTOMATIC_SEMANTIC_PROOF",
    }
