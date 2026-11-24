"""Reviewed cross-profile navigation and per-relation data gaps; never graph inference."""
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class IdentityGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    version: int = Field(ge=1)
    legal_name: str = Field(min_length=2, max_length=200)
    references: list[str] = Field(min_length=2, max_length=30)
    reviewed_at: AwareDatetime
    reviewer_id: str = Field(min_length=1, max_length=200)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]
    scope: str = Field(min_length=1, max_length=2000)


def apply_identities(data, raw_groups):
    if len(raw_groups) > 200:
        raise ValueError("Bounded identity groups required")
    refs = {r["id"]: r for r in data["entity_references"]}
    at = datetime.fromisoformat(data["as_of"])
    used, ids = set(), set()
    result = []
    for raw in raw_groups:
        group = IdentityGroup.model_validate(raw)
        if group.id in ids or group.reviewed_at > at:
            raise ValueError("Duplicate identity or future review")
        ids.add(group.id)
        profiles = set()
        for rid in group.references:
            ref = refs.get(rid)
            if rid in used or ref is None:
                raise ValueError("Unknown or multiply assigned identity reference")
            used.add(rid)
            if (not ref["eligible_at_snapshot"] or ref["resolution"] != "EXACT_ENTITY"
                    or ref["identity_level"] != "LEGAL_ENTITY"
                    or datetime.fromisoformat(ref["reviewed_at"]) > group.reviewed_at
                    or group.legal_name.casefold() not in {n.casefold() for n in ref["names"]}):
                raise ValueError("Identity requires current exact legal-name evidence and later review")
            profiles.add(ref["profile_id"])
        if len(profiles) < 2:
            raise ValueError("Cross-profile identity requires distinct profiles")
        result.append({**group.model_dump(mode="json"), "purpose": "REVIEWED_NAVIGATION_ONLY",
                       "automatic_cross_profile_propagation": False})
    data["identity_groups"] = result


def field_inventory(data):
    """No pooling facts across relations, no implied mechanism applicability or calibrated score."""
    eligible = {r["id"] for r in data["relations"] if r["eligible_at_snapshot"]}
    rows = []
    for exposure in data["exposures"]:
        for name, mechanism in data["mechanisms"].items():
            present, missing = [], []
            for field in mechanism["mitigants"]:
                fact = exposure["dimensions"].get(field, {})
                if exposure["relation_id"] in eligible and fact.get("status") == "SOURCED":
                    present.append({"field": field, "fact_id": fact["id"]})
                else:
                    missing.append(field)
            rows.append({"profile_id": exposure["profile_id"], "relation_id": exposure["relation_id"],
                         "mechanism_id": name, "present": present, "missing": missing,
                         "applicability": "NOT_ASSESSED", "period_alignment": "NOT_ASSESSED", "strength": "UNKNOWN",
                         "status": "FIELDS_PRESENT_SCOPE_REVIEW_REQUIRED" if not missing else "MISSING_FIELDS"})
    return rows
