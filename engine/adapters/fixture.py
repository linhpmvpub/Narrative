from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from engine.ingestion.contracts import StrictModel


class FixtureClaim(StrictModel):
    metric_id: str
    comparison_basis: str = Field(min_length=1)
    old_value: None
    new_value: None
    unit: None
    period: Literal["synthetic"]
    direction_for_demo: str


class FixtureMetadata(StrictModel):
    narrative_target: str
    illustrative_stance: str
    q_test_input: float | None = Field(default=None, ge=0, le=1)
    m_test_input: float | None = Field(default=None, ge=0, le=1)
    has_source_span: bool = False
    numeric_claims_must_not_be_inferred: bool = True
    reprint_of: str | None = None
    future_as_of_test: bool = False
    is_correction: bool = False
    supersedes: str | None = None


class FixtureEvent(StrictModel):
    event_id: str = Field(pattern=r"^F\d{3}$")
    canonical_event_key: str = Field(pattern=r"^SYN-F\d{3}$")
    source_document_id: str
    primary_entity_id: str
    driver_entity_id: str
    event_type: str
    headline_factual: str = Field(min_length=1, max_length=280)
    claim: FixtureClaim
    published_at: AwareDatetime
    first_seen_at: AwareDatetime
    available_at: AwareDatetime
    occurred_at: AwareDatetime | None
    source_url: str
    source_rights: Literal["approved_fixture_only"]
    is_synthetic: Literal[True]
    fixture_metadata: FixtureMetadata

    @model_validator(mode="after")
    def consistency(self) -> Self:
        if self.source_document_id != f"DOC-SYN-{self.event_id}":
            raise ValueError("Fixture document ID must match its input ID")
        if self.source_url != f"fixture://synthetic/{self.event_id}":
            raise ValueError("Fixture URL must identify its synthetic event")
        if self.available_at < max(self.published_at, self.first_seen_at):
            raise ValueError("Availability precedes publication or first observation")
        if self.claim.metric_id != self.driver_entity_id:
            raise ValueError("Fixture metric and driver disagree")
        meta = self.fixture_metadata
        if meta.is_correction != bool(meta.supersedes) or (meta.reprint_of and meta.is_correction):
            raise ValueError("Invalid correction/reprint declaration")
        return self


class FixtureSourceAdapter:
    def read(self, path: Path) -> list[FixtureEvent]:
        if path.stat().st_size > 10_000_000:
            raise ValueError("Fixture exceeds 10MB limit")
        records = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                if len(line) > 100_000:
                    raise ValueError(f"Oversized fixture line {number}")
                try:
                    records.append(FixtureEvent.model_validate_json(line))
                except ValueError as exc:
                    raise ValueError(f"Invalid fixture line {number}: {exc}") from exc
        if len({record.event_id for record in records}) != len(records):
            raise ValueError("Duplicate fixture input ID")
        # Deterministic import even when source lines are shuffled.
        return sorted(
            records,
            key=lambda item: (
                item.available_at,
                bool(item.fixture_metadata.reprint_of or item.fixture_metadata.is_correction),
                item.event_id,
            ),
        )
