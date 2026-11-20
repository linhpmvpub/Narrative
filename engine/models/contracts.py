from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Ticker = Literal["MU", "NVDA", "AMD", "DELL", "SNDK"]
Family = Literal[
    "CUSTOMER_DEMAND",
    "SUPPLIER_COST",
    "COMPETITOR_SUPPLY",
    "PRODUCT_MARKET",
    "MACRO_POLICY",
    "FINANCIAL_TRANSMISSION",
]


class SeedModel(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class Entity(SeedModel):
    entity_id: str = Field(min_length=1)
    entity_type: Literal[
        "company", "product_market", "driver", "financial_metric", "policy_or_constraint"
    ]
    display_name: str = Field(min_length=1)
    current_ticker: Ticker | None = None


class Stock(SeedModel):
    entity_id: str
    ticker: Ticker
    legal_name: str = Field(min_length=1)
    exchange: str
    cik: str | None = None
    identity_status: Literal["verify_via_sec_before_live"]
    independent_from: date | None = None

    @model_validator(mode="after")
    def identity(self) -> Self:
        if self.entity_id != f"CO_{self.ticker}" or self.cik is not None:
            raise ValueError("Seed identity must be canonical and SEC verification pending")
        if self.ticker == "SNDK" and self.independent_from != date(2025, 2, 21):
            raise ValueError("SNDK independence date must be explicit")
        return self


class Scope(BaseModel):
    max_hops: int = Field(ge=0, le=2)
    needs_user_confirmation_before_activation: Literal[True]


class Narrative(SeedModel):
    narrative_id: str = Field(min_length=1)
    primary_ticker: Ticker
    title: str = Field(min_length=1)
    thesis: str = Field(min_length=1)
    horizon_months: int = Field(ge=1, le=60)
    driver_ids: list[str] = Field(min_length=1, max_length=4)
    supporting_evidence: list[str] = Field(min_length=1)
    challenging_evidence: list[str] = Field(min_length=1)
    disconfirmation: str = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)
    watch_entities: list[str] = Field(min_length=1)
    scope: Scope
    version: int = Field(ge=1)
    status: Literal["template_draft"]
    is_template: Literal[True]
    hypothesis_polarity_for_company: Literal["favorable", "adverse"]
    stance_is_stock_direction: Literal[False]

    @model_validator(mode="after")
    def unique_drivers(self) -> Self:
        if len(set(self.driver_ids)) != len(self.driver_ids):
            raise ValueError("Duplicate driver")
        for values in (self.supporting_evidence, self.challenging_evidence, self.metrics):
            if any(not value.strip() for value in values):
                raise ValueError("Empty monitoring condition")
        return self


class NarrativeVersion(BaseModel):
    narrative_id: str
    version_number: int = Field(ge=1)
    config: Narrative
    published_at: AwareDatetime
    available_at: AwareDatetime

    @model_validator(mode="after")
    def clocks(self) -> Self:
        if self.available_at < self.published_at:
            raise ValueError("Availability precedes publication")
        if (
            self.narrative_id != self.config.narrative_id
            or self.version_number != self.config.version
        ):
            raise ValueError("Version identity mismatch")
        return self


class NarrativeDriver(BaseModel):
    narrative_version_id: str
    driver_entity_id: str
    priority: int = Field(ge=1, le=5)


class Relationship(SeedModel):
    relation_id: str
    from_entity: str
    to_entity: str
    family: Family
    mechanism: str = Field(min_length=1)
    sign: Literal["positive", "negative", "conditional", "unknown"]
    lag: Literal["immediate", "short", "long", "variable"]
    strength: Decimal | None = Field(default=None, ge=0, le=1)
    confidence: Decimal = Field(ge=0, le=1)
    status: Literal["candidate", "verified", "rejected", "stale"]
    evidence_ids: list[str]
    recorded_at: AwareDatetime
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    reviewed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def temporal(self) -> Self:
        if self.from_entity == self.to_entity:
            raise ValueError("Self edge")
        if self.valid_until and (not self.valid_from or self.valid_until <= self.valid_from):
            raise ValueError("Invalid relation validity interval")
        if self.status == "verified" and (not self.evidence_ids or not self.reviewed_at):
            raise ValueError("Verified edge requires evidence review")
        return self


def utc(value: datetime) -> datetime:
    """SQLite drops timezone metadata; database timestamps are always UTC."""
    from datetime import UTC

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
