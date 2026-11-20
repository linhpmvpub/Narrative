import hashlib
import json
from decimal import Decimal
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class SourceSpan(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Empty or inverted source span")
        return self


class MeasurementBasis(StrictModel):
    concept: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    duration: Literal["quarter", "year", "instant", "other"]
    fiscal_calendar: str = Field(min_length=1)
    accounting_basis: str = Field(min_length=1)
    observation_kind: Literal["actual", "guidance", "price"]


class NumericOrQualitativeClaim(StrictModel):
    claim_text: str = Field(min_length=1, max_length=4000)
    metric_id: str | None
    unit: str | None
    period: str | None
    comparison_basis: str = Field(min_length=1)
    old_value: Decimal | None
    new_value: Decimal | None
    source_span: SourceSpan
    source_url: str = Field(min_length=1)
    old_basis: MeasurementBasis | None = None
    new_basis: MeasurementBasis | None = None

    @model_validator(mode="after")
    def comparable(self) -> Self:
        if self.old_value is not None or self.new_value is not None:
            if not self.metric_id or not self.unit or not self.period or not self.new_basis:
                raise ValueError("Numeric claim requires concept, unit, period and basis")
            if self.new_basis.concept != self.metric_id or self.new_basis.unit != self.unit:
                raise ValueError("Claim and measurement basis disagree")
        if self.old_value is not None and self.new_value is not None:
            if self.old_basis != self.new_basis:
                raise ValueError(
                    "Incompatible unit, concept, duration, calendar or accounting basis"
                )
        return self


class EventExtraction(StrictModel):
    source_document_id: str = Field(min_length=1)
    entity_ids: list[str] = Field(min_length=1)
    event_type: str = Field(min_length=1)
    factual_headline: str = Field(min_length=1, max_length=280)
    published_at: AwareDatetime
    available_at: AwareDatetime
    claims: list[NumericOrQualitativeClaim] = Field(min_length=1, max_length=20)
    uncertainties: list[str]

    @model_validator(mode="after")
    def clocks(self) -> Self:
        if self.available_at < self.published_at:
            raise ValueError("Availability cannot precede publication")
        return self

    def validate_source(self, text: str, source_url: str) -> None:
        for claim in self.claims:
            if claim.source_url != source_url or claim.source_span.end > len(text):
                raise ValueError("Claim must reference the supplied document and valid offsets")
            if text[claim.source_span.start : claim.source_span.end] != claim.claim_text:
                raise ValueError("Claim is not the cited source passage")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def canonical_key(
    *, issuer: str, event_type: str, metric: str, period: str, basis: str, occurrence_window: str
) -> str:
    """No headline/URL in the economic-fact key. Missing identity fails closed."""
    parts = [issuer, event_type, metric, period, basis, occurrence_window]
    if any(not x.strip() for x in parts):
        raise ValueError("Insufficient canonical identity")
    return "EV-" + digest([" ".join(x.split()).casefold() for x in parts])
