"""Temporal news snapshots over synthetic sources and isolated stores."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_news import CONFIG
from test_news_claims import approval
from test_news_claims import setup as setup
from test_news_ingestion import enabled as enabled
from test_news_ingestion import ready, send
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.ingestion.reviewed import sources, versions
from engine.models.schema_v14 import news_claim_intakes
from engine.news import save_rows
from engine.news_snapshot import snapshot


def read(client, identities, at=None, actor=3):
    return client.get(
        "/api/v0/news-claims/canonical",
        params={"as_of": at.isoformat()} if at else {},
        headers=headers(identities[actor]),
    )


def test_cutoff_revision_correction_and_no_fallback(db, client, identities, setup, enabled):
    item, payload, rows = setup
    claim, body = ready(client, identities, payload)
    before = datetime.now(UTC)
    first = send(client, identities, claim, body).json()
    cutoff = datetime.now(UTC)
    assert read(client, identities, before).json()["items"] == []
    old = read(client, identities, cutoff).json()
    assert old["items"][0]["event_version_id"] == first["event_version_id"], old
    changed = deepcopy(rows)
    changed[0]["title"] += " corrected"
    with db.begin() as conn:
        save_rows(
            conn, {"id": CONFIG["id"], "config": CONFIG}, changed, "b" * 64, datetime.now(UTC)
        )
    gap = datetime.now(UTC)
    assert read(client, identities, gap).json()["items"] == []
    assert read(client, identities, cutoff).json()["items"] == old["items"]
    source = client.get("/api/v0/news-claims/source/" + item, headers=headers(identities[0])).json()
    payload.update(
        revision_id=source["revision_id"], expected_payload_sha256=source["payload_sha256"]
    )
    payload["claim"].update(
        claim_text=source["text"], source_span={"start": 0, "end": len(source["text"])}
    )
    correction, correction_body = ready(client, identities, payload)
    correction_body.update(action="correction", target_claim_id=claim)
    assert send(client, identities, correction, correction_body).status_code == 200
    after = datetime.now(UTC)
    result = read(client, identities, after).json()
    assert len(result["items"]) == 1 and result["items"][0]["version"] == 2, result
    assert read(client, identities, gap).json()["items"] == []
    revoked = client.post(
        f"/api/v0/news-claims/{correction}/reviews",
        json=approval(expected_review_version=1, decision="revoked"),
        headers=headers(identities[3]),
    )
    assert revoked.status_code == 200
    now = read(client, identities).json()
    assert now["items"] == [] and len(now["withheld"]) == 1
    assert read(client, identities, after).json()["items"] == result["items"]
    assert read(client, identities, cutoff).json()["items"] == old["items"]


def test_duplicate_cannot_rescue_revoked_primary(db, client, identities, setup, enabled):
    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    duplicate, dupbody = ready(client, identities, setup[1])
    dupbody.update(action="duplicate", target_claim_id=claim)
    assert send(client, identities, duplicate, dupbody).status_code == 200
    assert len(read(client, identities).json()["items"]) == 1
    client.post(
        f"/api/v0/news-claims/{claim}/reviews",
        json=approval(expected_review_version=1, decision="revoked"),
        headers=headers(identities[3]),
    )
    assert read(client, identities).json()["items"] == []


def test_authorization_time_limits_and_current_block(
    db, client, identities, setup, enabled, monkeypatch
):
    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    cutoff = datetime.now(UTC)
    assert read(client, identities, actor=0).status_code == 403
    assert client.get("/api/v0/news-claims/canonical").status_code == 401
    assert read(client, identities, cutoff + timedelta(days=1)).status_code == 409
    assert read(client, identities, cutoff.replace(tzinfo=None)).status_code == 409
    assert (
        client.get(
            "/api/v0/news-claims/canonical?limit=501", headers=headers(identities[3])
        ).status_code
        == 422
    )
    with db.begin() as conn:
        conn.execute(sources.update().values(rights_status="blocked"))
    result = read(client, identities, cutoff).json()
    assert result["items"] == [] and "blocked" in result["withheld"][0]["reason"]
    assert result["source_block_policy"] == "CURRENT_BLOCK_OVERRIDES_HISTORICAL_SNAPSHOT"
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    assert read(client, identities).status_code == 409
    from engine.mobile_gateway import allowed

    assert not allowed("GET", "/api/v0/news-claims/canonical")


@pytest.mark.parametrize("tamper", ["intake_hash", "receipt_time", "canonical_fact"])
def test_corrupt_provenance_withheld(db, client, identities, setup, enabled, tamper):
    from engine.models.schema_v15 import news_promotions

    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    with db.begin() as conn:
        if tamper == "intake_hash":
            conn.execute(news_claim_intakes.update().values(payload_sha256="0" * 64))
        elif tamper == "receipt_time":
            conn.execute(
                news_promotions.update().values(recorded_at=datetime.now(UTC) - timedelta(days=1))
            )
        else:
            value = deepcopy(conn.scalar(select(versions.c.normalized_claim)))
            value["fact"]["claim_text"] = "tampered"
            conn.execute(versions.update().values(normalized_claim=value))
    result = read(client, identities).json()
    assert result["items"] == [] and len(result["withheld"]) == 1, result


def test_limit_and_read_only(db, client, identities, setup, enabled):
    from sqlalchemy import func

    from engine.models.schema_v15 import news_promotions

    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    second, b2 = ready(client, identities, setup[1])
    b2["occurrence_window"] = "another synthetic occurrence"
    send(client, identities, second, b2)
    with db.connect() as conn:
        result = snapshot(conn, datetime.now(UTC), 1)
        assert result["truncated"] and result["examined"] == 1 and len(result["items"]) == 1
        assert conn.scalar(select(func.count()).select_from(news_promotions)) == 2
        assert conn.scalar(select(func.count()).select_from(news_claim_intakes)) == 2
