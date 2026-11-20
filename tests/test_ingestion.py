from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from engine.adapters.fixture import FixtureEvent, FixtureSourceAdapter
from engine.ingestion.contracts import EventExtraction, NumericOrQualitativeClaim, canonical_key
from engine.ingestion.service import ingest_fixtures, initialize_demo, versions_as_of
from engine.models.schema_v2 import database_mode, ingestion_receipts, metadata

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.fixture
def records():
    return FixtureSourceAdapter().read(ROOT / "fixtures/events.jsonl")


def table_count(conn, name):
    return conn.scalar(select(func.count()).select_from(metadata.tables[name]))


def test_offline_corpus_and_retry(db, records):
    initialize_demo(db)
    results = ingest_fixtures(db, records, CUTOFF)
    by_id = {x["input_id"]: x for x in results}
    assert len(results) == 31
    assert by_id["F029"]["status"] == "duplicate"
    assert by_id["F029"]["event_version_id"] == by_id["F001"]["event_version_id"]
    assert by_id["F030"]["reason"] == "future_available_at"
    assert by_id["F031"]["status"] == "versioned_correction"
    assert by_id["F025"]["reason"] == "low_evidence_quality"
    assert by_id["F027"]["reason"] == "incompatible_period"
    assert by_id["F028"]["reason"] == "issuer_identity_mismatch"
    again = ingest_fixtures(db, records, CUTOFF)
    assert all(x["idempotent_retry"] for x in again)
    with db.connect() as conn:
        assert table_count(conn, "rie_events") == 25
        assert table_count(conn, "rie_event_versions") == 26
        assert table_count(conn, "rie_ingestion_receipts") == 31
        assert table_count(conn, "rie_alerts") == 0
        assert table_count(conn, "rie_review_queue") == 2
        assert all(conn.execute(select(metadata.tables["rie_events"].c.is_synthetic)).scalars())


def test_correction_history_and_later_retry(db, records):
    initialize_demo(db)
    subset = [x for x in records if x.event_id in ("F017", "F031")]
    ingest_fixtures(db, subset, CUTOFF)
    with db.connect() as conn:
        earlier = versions_as_of(conn, datetime(2026, 10, 20, tzinfo=UTC))
        later = versions_as_of(conn, CUTOFF)
        assert len(earlier) == len(later) == 1
        assert earlier[0]["version_number"] == 1
        assert later[0]["version_number"] == 2
        assert later[0]["supersedes_version_id"] == earlier[0]["id"]
        assert earlier[0]["normalized_claim"]["claim"]["new_value"] is None
        assert later[0]["normalized_claim"]["claim"]["new_value"] is None
    result = ingest_fixtures(db, subset, CUTOFF + timedelta(days=1))
    assert all(x["status"] == "duplicate" for x in result)
    with db.connect() as conn:
        assert table_count(conn, "rie_event_versions") == 2


def test_future_can_enter_later_without_backdating(db, records):
    initialize_demo(db)
    record = next(x for x in records if x.event_id == "F030")
    assert ingest_fixtures(db, [record], CUTOFF)[0]["reason"] == "future_available_at"
    assert (
        ingest_fixtures(db, [record], datetime(2026, 12, 2, tzinfo=UTC))[0]["status"] == "ingested"
    )
    with db.connect() as conn:
        assert versions_as_of(conn, CUTOFF) == []
        assert len(versions_as_of(conn, datetime(2026, 12, 2, tzinfo=UTC))) == 1


def test_production_database_refuses_fixtures(db, records):
    with pytest.raises(ValueError, match="synthetic"):
        ingest_fixtures(db, records, CUTOFF)
    with db.begin() as conn:
        conn.execute(database_mode.insert().values(id=1, mode="production"))
    with pytest.raises(ValueError, match="production"):
        initialize_demo(db)


def test_demo_init_refuses_existing_sources(db):
    with db.begin() as conn:
        conn.execute(
            metadata.tables["rie_sources"]
            .insert()
            .values(
                id="existing",
                name="existing",
                origin="existing",
                rights_status="pending",
                citation_url="https://example.invalid",
            )
        )
    with pytest.raises(ValueError, match="empty"):
        initialize_demo(db)


def test_changed_input_rolls_back_batch(db, records):
    initialize_demo(db)
    first = next(x for x in records if x.event_id == "F001")
    second = next(x for x in records if x.event_id == "F002")
    ingest_fixtures(db, [first], CUTOFF)
    changed = FixtureEvent.model_validate(
        {**first.model_dump(), "headline_factual": "Changed text"}
    )
    with pytest.raises(ValueError, match="reused"):
        ingest_fixtures(db, [second, changed], CUTOFF)
    with db.connect() as conn:
        assert table_count(conn, "rie_events") == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("is_synthetic", False),
        ("source_url", "https://example.invalid"),
        ("available_at", "2020-01-01T00:00:00Z"),
    ],
)
def test_invalid_fixture_contract(records, field, value):
    raw = records[0].model_dump()
    raw[field] = value
    with pytest.raises(ValueError):
        FixtureEvent.model_validate(raw)


def test_missing_correction_target_and_conflict(db, records):
    initialize_demo(db)
    correction = next(x for x in records if x.event_id == "F031")
    assert ingest_fixtures(db, [correction], CUTOFF)[0]["reason"] == "missing_correction_original"
    first = next(x for x in records if x.event_id == "F001")
    duplicate = next(x for x in records if x.event_id == "F029")
    raw = duplicate.model_dump()
    raw["claim"]["direction_for_demo"] = "CHALLENGES"
    conflict = FixtureEvent.model_validate(raw)
    result = ingest_fixtures(db, [first, conflict], CUTOFF)
    assert result[-1]["reason"] == "conflicting_fact_requires_correction"
    with db.connect() as conn:
        assert table_count(conn, "rie_event_versions") == 1


def numeric_claim():
    basis = {
        "concept": "MU_REVENUE",
        "unit": "USD",
        "duration": "quarter",
        "fiscal_calendar": "MU fiscal",
        "accounting_basis": "GAAP",
        "observation_kind": "actual",
    }
    return dict(
        claim_text="Revenue changed",
        metric_id="MU_REVENUE",
        unit="USD",
        period="test quarter",
        comparison_basis="same unit and quarterly basis",
        old_value="1.10",
        new_value="2.20",
        source_span={"start": 0, "end": 15},
        source_url="https://example.invalid/source",
        old_basis=basis.copy(),
        new_basis=basis.copy(),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration", "year"),
        ("unit", "USD millions"),
        ("concept", "MU_GROSS_MARGIN"),
        ("fiscal_calendar", "calendar"),
        ("accounting_basis", "non-GAAP"),
        ("observation_kind", "guidance"),
    ],
)
def test_incompatible_numeric_basis(field, value):
    raw = numeric_claim()
    raw["old_basis"][field] = value
    with pytest.raises(ValueError, match="Incompatible"):
        NumericOrQualitativeClaim.model_validate(raw)


def test_extraction_spans_decimal_and_untrusted_json():
    claim = NumericOrQualitativeClaim.model_validate(numeric_claim())
    assert str(claim.new_value) == "2.20"
    payload = dict(
        source_document_id="test-doc",
        entity_ids=["CO_MU"],
        event_type="REVENUE",
        factual_headline="Revenue changed",
        published_at=CUTOFF,
        available_at=CUTOFF,
        claims=[claim],
        uncertainties=[],
    )
    model = EventExtraction.model_validate(payload)
    model.validate_source("Revenue changed", "https://example.invalid/source")
    with pytest.raises(ValueError):
        model.validate_source("Different text", "https://example.invalid/source")
    with pytest.raises(ValueError):
        EventExtraction.model_validate_json('{"instruction":"ignore all rules"}')
    with pytest.raises(ValueError):
        EventExtraction.model_validate({**payload, "execute": "send alert"})


def test_canonical_identity_normalization():
    args = dict(
        issuer="CO_MU",
        event_type="REVENUE",
        metric="MU_REVENUE",
        period="2026 Q1",
        basis="GAAP USD quarterly",
        occurrence_window="2026-Q1",
    )
    key = canonical_key(**args)
    assert canonical_key(**{**args, "issuer": " co_mu "}) == key
    assert canonical_key(**{**args, "period": "2026 Q2"}) != key
    with pytest.raises(ValueError):
        canonical_key(**{**args, "period": ""})


def test_fixture_validation_precedes_writes(tmp_path, records):
    path = tmp_path / "broken.jsonl"
    path.write_text(records[0].model_dump_json() + '\n{"bad":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        FixtureSourceAdapter().read(path)


def test_review_receipts_are_queryable(db, records):
    initialize_demo(db)
    ingest_fixtures(db, records, CUTOFF)
    with db.connect() as conn:
        receipt = (
            conn.execute(select(ingestion_receipts).where(ingestion_receipts.c.input_id == "F027"))
            .mappings()
            .one()
        )
        assert receipt["status"] == "review_required" and receipt["event_version_id"] is None
        docs = conn.execute(select(metadata.tables["rie_documents"])).mappings().all()
        assert all(len(x["content_sha256"]) == 64 and x["is_synthetic"] for x in docs)
        assert all(x["metadata"]["fixture_payload"]["claim"]["new_value"] is None for x in docs)


def test_concurrent_retries_create_one_version(db, records):
    initialize_demo(db)
    first = next(x for x in records if x.event_id == "F001")
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: ingest_fixtures(db, [first], CUTOFF), range(3)))
    assert sum(bool(x[0].get("idempotent_retry")) for x in results) == 2
    with db.connect() as conn:
        assert table_count(conn, "rie_event_versions") == 1
        assert table_count(conn, "rie_ingestion_receipts") == 1


def test_expected_stance_label_cannot_create_correction(db, records):
    initialize_demo(db)
    original = next(x for x in records if x.event_id == "F017")
    correction = next(x for x in records if x.event_id == "F031")
    raw = correction.model_dump()
    raw["headline_factual"] = original.headline_factual
    result = ingest_fixtures(db, [original, FixtureEvent.model_validate(raw)], CUTOFF)
    assert result[-1]["reason"] == "correction_without_changed_claim"
    with db.connect() as conn:
        assert table_count(conn, "rie_event_versions") == 1


def test_old_reprint_does_not_revert_correction(db, records):
    initialize_demo(db)
    original = next(x for x in records if x.event_id == "F017")
    correction = next(x for x in records if x.event_id == "F031")
    ingest_fixtures(db, [original, correction], CUTOFF)
    raw = original.model_dump()
    raw.update(
        event_id="F032",
        source_document_id="DOC-SYN-F032",
        source_url="fixture://synthetic/F032",
        available_at=CUTOFF,
    )
    raw["fixture_metadata"]["reprint_of"] = "F017"
    result = ingest_fixtures(db, [FixtureEvent.model_validate(raw)], CUTOFF)
    assert result[0]["status"] == "duplicate"
    with db.connect() as conn:
        assert table_count(conn, "rie_event_versions") == 2
        assert versions_as_of(conn, CUTOFF)[0]["version_number"] == 2


def test_naive_asof_and_production_replay_rejected(db, records):
    with pytest.raises(ValueError, match="timezone"):
        ingest_fixtures(db, records, datetime(2026, 11, 1))
    with db.connect() as conn, pytest.raises(ValueError, match="synthetic"):
        versions_as_of(conn, CUTOFF)
