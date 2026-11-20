import json
import shutil
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from engine.api import app
from engine.graph.review import approve_relationship, live_edge_eligible
from engine.identity import resolve_ticker, validate_metric_issuer
from engine.models import EntityRecord
from engine.models.contracts import NarrativeVersion, Relationship
from engine.models.schema_v1 import metadata
from engine.seed import read_config, seed
from engine.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def count(conn, name):
    return conn.scalar(select(func.count()).select_from(metadata.tables[name]))


def test_g01_cardinality_idempotent_and_orm(db):
    seed(db, ROOT / "config")
    with db.connect() as conn:
        assert count(conn, "rie_entities") == 42
        assert count(conn, "rie_entity_aliases") == 5
        assert count(conn, "rie_narratives") == 10
        assert count(conn, "rie_narrative_versions") == 10
        assert count(conn, "rie_relationships") == 40
        t = metadata.tables["rie_narratives"]
        assert sorted(
            conn.execute(
                select(t.c.ticker_entity_id, func.count()).group_by(t.c.ticker_entity_id)
            ).all()
        ) == [(f"CO_{x}", 2) for x in ("AMD", "DELL", "MU", "NVDA", "SNDK")]
    with Session(db) as session:
        assert session.get(EntityRecord, "CO_SNDK") is not None


def test_all_reference_tables_migrated(db):
    assert set(metadata.tables) <= set(inspect(db).get_table_names())


def test_postgresql_ddl_compiles_with_native_types():
    # Compilation is not PostgreSQL runtime validation; CI runs the latter.
    ddl = "\n".join(
        str(CreateTable(t).compile(dialect=postgresql.dialect())) for t in metadata.sorted_tables
    )
    assert "JSONB" in ddl and "TIMESTAMP WITH TIME ZONE" in ddl and "UUID" in ddl


def test_backdated_review_does_not_backdate_recording(db):
    evidence_id = add_evidence(db)
    reviewed_at = datetime.now(UTC) - timedelta(milliseconds=100)
    approve(db, [evidence_id], reviewed_at=reviewed_at)
    with db.connect() as conn:
        assert not live_edge_eligible(conn, "R026", reviewed_at)
        assert live_edge_eligible(conn, "R026", datetime.now(UTC))


def test_g02_all_candidate_edges_ineligible(db):
    with db.connect() as conn:
        for index in range(1, 41):
            assert not live_edge_eligible(conn, f"R{index:03}", datetime.now(UTC))


def test_identity_pending_and_sndk_dates(db):
    with db.connect() as conn:
        assert resolve_ticker(conn, "SNDK", date(2026, 1, 1)) is None
        assert resolve_ticker(conn, "WDC", date(2026, 1, 1), require_verified=False) is None
        assert resolve_ticker(conn, "SNDK", date(2025, 2, 23), require_verified=False) is None
        assert resolve_ticker(conn, "SNDK", date(2025, 2, 24), require_verified=False) == "CO_SNDK"


@pytest.mark.parametrize(
    "issuer,day",
    [("CO_WDC", date(2026, 1, 1)), ("CO_SNDK", date(2025, 2, 20)), ("CO_MU", date(2026, 1, 1))],
)
def test_g12_metric_identity_rejected(issuer, day):
    with pytest.raises(ValueError):
        validate_metric_issuer(issuer, "SNDK_REVENUE", day)


def test_sndk_post_separation_metric():
    validate_metric_issuer("CO_SNDK", "SNDK_REVENUE", date(2025, 2, 21))


@pytest.mark.parametrize(
    "file,mutation",
    [
        ("stocks", lambda x: x.pop()),
        ("entities", lambda x: x.append(x[0])),
        ("entities", lambda x: x[0].update(entity_type="alien")),
        ("relationships", lambda x: x[0].update(to_entity="UNKNOWN")),
        ("relationships", lambda x: x[0].update(status="verified")),
        ("relationships", lambda x: x[0].update(strength=0.6)),
        ("relationships", lambda x: x[0].update(recorded_at="2026-01-01")),
        (
            "relationships",
            lambda x: x[0].update(
                valid_from="2026-11-20T00:00:00Z", valid_until="2026-11-19T00:00:00Z"
            ),
        ),
        ("narratives", lambda x: x[0].update(driver_ids=["UNKNOWN"])),
        ("narratives", lambda x: x[0].update(driver_ids=["AI_CAPEX", "AI_CAPEX"])),
        ("narratives", lambda x: x[0].update(supporting_evidence=[])),
        ("narratives", lambda x: x[0].update(disconfirmation=" ")),
        ("narratives", lambda x: x[0]["scope"].update(max_hops=3)),
    ],
)
def test_invalid_seed_rejected_before_write(tmp_path, file, mutation):
    path = tmp_path / "config"
    shutil.copytree(ROOT / "config", path)
    values = json.loads((path / f"{file}.json").read_text())
    mutation(values)
    (path / f"{file}.json").write_text(json.dumps(values))
    with pytest.raises(ValueError):
        read_config(path)


def test_narrative_version_not_overwritten(db, tmp_path):
    path = tmp_path / "config"
    shutil.copytree(ROOT / "config", path)
    values = json.loads((path / "narratives.json").read_text())
    values[0]["thesis"] = "Changed hypothesis"
    (path / "narratives.json").write_text(json.dumps(values))
    with pytest.raises(ValueError, match="immutable"):
        seed(db, path)
    with db.connect() as conn:
        assert count(conn, "rie_narrative_versions") == 10


def add_evidence(db, **overrides):
    now = datetime.now(UTC) - timedelta(seconds=1)
    doc_id, evidence_id = str(uuid4()), str(uuid4())
    with db.begin() as conn:
        conn.execute(
            metadata.tables["rie_sources"]
            .insert()
            .values(
                id="test-source",
                name="Unit test source",
                origin="test",
                rights_status=overrides.get("rights", "approved"),
                citation_url="https://example.invalid/test",
            )
        )
        conn.execute(
            metadata.tables["rie_documents"]
            .insert()
            .values(
                id=doc_id,
                source_id="test-source",
                source_url="https://example.invalid/test",
                content_sha256="a" * 64,
                published_at=now,
                first_seen_at=now,
                available_at=overrides.get("available_at", now),
                retrieved_at=now,
                is_synthetic=overrides.get("synthetic", False),
            )
        )
        conn.execute(
            metadata.tables["rie_evidence"]
            .insert()
            .values(
                id=evidence_id,
                document_id=doc_id,
                text_start=0,
                text_end=overrides.get("text_end", 10),
                quoted_claim="Unit test only",
                url=overrides.get("url", "https://example.invalid/test"),
                verified_by="test-reviewer",
                verified_at=now,
                created_at=now,
            )
        )
    return evidence_id


def approve(db, ids, **overrides):
    now = datetime.now(UTC)
    kwargs = dict(
        evidence_ids=ids,
        reviewer="reviewer",
        reason="Unit test review",
        reviewed_at=now,
        valid_from=now - timedelta(days=1),
        strength=Decimal("0.6"),
        confidence=Decimal("0.9"),
        routing_basis="medium qualitative band; exposure unknown",
    )
    kwargs.update(overrides)
    approve_relationship(db, "R026", **kwargs)


@pytest.mark.parametrize(
    "mode",
    ["empty", "unknown", "synthetic", "rights", "future", "url", "offset", "reviewer", "basis"],
)
def test_invalid_approval_atomic(db, mode):
    changes = {
        "synthetic": {"synthetic": True},
        "rights": {"rights": "pending"},
        "future": {"available_at": datetime.now(UTC) + timedelta(days=1)},
        "url": {"url": "fixture://synthetic"},
        "offset": {"text_end": 0},
    }.get(mode, {})
    evidence_id = add_evidence(db, **changes)
    ids = [] if mode == "empty" else [str(uuid4()) if mode == "unknown" else evidence_id]
    kwargs = (
        {"reviewer": ""} if mode == "reviewer" else {"routing_basis": ""} if mode == "basis" else {}
    )
    with pytest.raises(ValueError):
        approve(db, ids, **kwargs)
    with db.connect() as conn:
        assert count(conn, "rie_relationship_revisions") == 0
        assert count(conn, "rie_relationship_evidence") == 0
        assert not live_edge_eligible(conn, "R026", datetime.now(UTC))


def test_approval_audit_asof_and_reseed(db):
    evidence_id = add_evidence(db)
    before = datetime.now(UTC)
    approve(db, [evidence_id])
    seed(db, ROOT / "config")
    with db.connect() as conn:
        assert not live_edge_eligible(conn, "R026", before)
        assert live_edge_eligible(conn, "R026", datetime.now(UTC))
        rev = conn.execute(select(metadata.tables["rie_relationship_revisions"])).mappings().one()
        assert rev["before"]["status"] == "candidate"
        assert rev["after"]["status"] == "verified"
        assert rev["reviewer_id"] == "reviewer"
    with pytest.raises(ValueError):
        approve(db, [evidence_id])


def test_narrative_not_visible_before_import(db):
    t = metadata.tables["rie_narrative_versions"]
    with db.connect() as conn:
        assert (
            conn.execute(
                select(t).where(t.c.available_at <= datetime(2026, 11, 1, tzinfo=UTC))
            ).first()
            is None
        )


def test_database_fk_and_verified_guard(db):
    t = metadata.tables["rie_relationships"]
    for values in ({"to_entity_id": "UNKNOWN"}, {"status": "verified"}):
        with pytest.raises(IntegrityError), db.begin() as conn:
            conn.execute(t.update().where(t.c.id == "R026").values(**values))


@pytest.mark.parametrize("name", ["SEND_NOTIFICATIONS", "ALLOW_SYNTHETIC_LIVE", "LLM_MODE"])
def test_unsafe_settings_rejected(monkeypatch, name):
    monkeypatch.setenv(name, "true")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_api_catalog_auth_and_readiness(db, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "unit-test-token")
    with TestClient(app) as client:
        assert client.get("/healthz").json()["delivery"] == "disabled"
        assert client.get("/readyz").status_code == 200
        assert client.get("/api/v0/stocks").status_code == 401
        assert (
            client.get("/api/v0/stocks", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )
        headers = {"Authorization": "Bearer unit-test-token"}
        assert len(client.get("/api/v0/stocks", headers=headers).json()["items"]) == 5
        assert (
            len(client.get("/api/v0/narratives/templates", headers=headers).json()["items"]) == 10
        )


def test_readiness_requires_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty.db'}")
    with TestClient(app) as client:
        assert client.get("/readyz").status_code == 503


def test_missing_api_token_denies_access(db, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    with TestClient(app) as client:
        assert (
            client.get("/api/v0/stocks", headers={"Authorization": "Bearer arbitrary"}).status_code
            == 401
        )


def test_pydantic_version_clock():
    narrative = read_config(ROOT / "config")["narratives"][0]
    with pytest.raises(ValueError):
        NarrativeVersion(
            narrative_id="N01",
            version_number=1,
            config=narrative,
            published_at="2026-11-19T00:00:00Z",
            available_at="2026-11-01T00:00:00Z",
        )


def test_relation_self_loop():
    item = read_config(ROOT / "config")["relationships"][0].model_dump()
    item["to_entity"] = item["from_entity"]
    with pytest.raises(ValueError):
        Relationship.model_validate(item)
