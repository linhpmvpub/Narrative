"""Reviewed product scope comparison, separate from identity and impact routing.

The finite sets use the same reviewer-defined vocabulary version. Missing dimensions
are unknown, never universal exposure. Interval bounds preserve exclusive endpoints.
This module does not classify news, approve synonyms or authorize financial impact.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lower: Decimal = Field(ge=0, allow_inf_nan=False)
    upper: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    @model_validator(mode="after")
    def valid(self):
        if self.upper is not None and (
            self.upper < self.lower
            or (self.upper == self.lower and not (self.lower_inclusive and self.upper_inclusive))
        ):
            raise ValueError("Empty/reversed process interval")
        return self


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vocabulary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    # None means not specified. Lists are exhaustive for the declared scope only.
    products: frozenset[str] | None = None
    materials: frozenset[str] | None = None
    geographies: frozenset[str] | None = None
    process_nm: NodeRange | None = None

    @model_validator(mode="after")
    def nonempty(self):
        for name in ["products", "materials", "geographies"]:
            values = getattr(self, name)
            if values is not None and (
                not values
                or len(values) > 100
                or any(not v.strip() or v != v.strip() or len(v) > 100 for v in values)
            ):
                raise ValueError("Nonempty bounded canonical IDs required")
        return self


class ScopeAnnotation(BaseModel):
    """Source-bound interpretation; literal grounding is not semantic validation."""

    model_config = ConfigDict(extra="forbid")
    scope: Scope
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=8000)
    reviewer_id: str = Field(min_length=1)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]
    interpretation_status: Literal["REVIEWER_DECLARED_NOT_INDEPENDENT_GOLD"]

    def check_source(self, text):
        import hashlib

        if (
            hashlib.sha256(text.encode()).hexdigest() != self.text_sha256
            or not 0 <= self.start < self.end <= len(text)
            or text[self.start : self.end] != self.quote
        ):
            raise ValueError("Scope annotation source changed")


def interval_subset(a, b):
    lower_ok = a.lower > b.lower or (
        a.lower == b.lower and (not a.lower_inclusive or b.lower_inclusive)
    )
    upper_ok = b.upper is None or (
        a.upper is not None
        and (
            a.upper < b.upper
            or (a.upper == b.upper and (not a.upper_inclusive or b.upper_inclusive))
        )
    )
    return lower_ok and upper_ok


def interval_disjoint(a, b):
    return any(
        x.upper is not None
        and (
            x.upper < y.lower
            or (x.upper == y.lower and not (x.upper_inclusive and y.lower_inclusive))
        )
        for x, y in [(a, b), (b, a)]
    )


def compare(event: Scope, exposure: Scope):
    """Set relation of event scope to company exposure, never economic strength."""
    if event.vocabulary_sha256 != exposure.vocabulary_sha256:
        raise ValueError("Incompatible scope vocabularies")
    dimensions = {}
    for name in ["products", "materials", "geographies", "process_nm"]:
        a, b = getattr(event, name), getattr(exposure, name)
        if a is None or b is None:
            dimensions[name] = "UNKNOWN"
            continue
        if name == "process_nm":
            disjoint = interval_disjoint(a, b)
            ab, ba = interval_subset(a, b), interval_subset(b, a)
        else:
            disjoint, ab, ba = a.isdisjoint(b), a <= b, b <= a
        dimensions[name] = (
            "DISJOINT"
            if disjoint
            else "EXACT"
            if ab and ba
            else "NARROWER"
            if ab
            else "BROADER"
            if ba
            else "PARTIAL_OVERLAP"
        )
    known = set(dimensions.values())
    if "DISJOINT" in known:
        status = "DISJOINT"
    elif "UNKNOWN" in known:
        status = "UNKNOWN"
    elif known == {"EXACT"}:
        status = "EXACT"
    elif known <= {"EXACT", "NARROWER"}:
        status = "NARROWER"
    elif known <= {"EXACT", "BROADER"}:
        status = "BROADER"
    else:
        status = "PARTIAL_OVERLAP"
    return {
        "relation": status,
        "dimensions": dimensions,
        "delivery": "disabled",
        "impact_authorized": False,
        "financial_magnitude": "UNKNOWN",
        "limitation": "Reviewer-declared scope only; source, identity and route gates still required",
    }
