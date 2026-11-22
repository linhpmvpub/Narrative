"""Shared informational projection excludes private review material and stale records."""

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select
from test_news import CONFIG
from test_news_claims import approval
from test_news_claims import setup as setup
from test_news_ingestion import enabled as enabled
from test_news_ingestion import ready, send
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.ingestion.reviewed import sources
from engine.news import save_rows


def feed(client, identities, actor=0, **params):
    return client.get("/api/v0/news/reviewed", params=params, headers=headers(identities[actor]))


def test_shared_projection_is_allowlisted(client, identities, setup, enabled):
    payload = deepcopy(setup[1])
    payload["uncertainties"] = ["PRIVATE REVIEW NOTE MUST NOT BE SHARED"]
    payload["claim"]["comparison_basis"] = "PRIVATE BASIS NOTE MUST NOT BE SHARED"
    claim, body = ready(client, identities, payload)
    send(client, identities, claim, body)
    response = feed(client, identities)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["mode"] == "REVIEWED_INFORMATIONAL_NEWS" and result["delivery"] == "disabled"
    card = result["items"][0]
    assert card["excerpt"] == payload["claim"]["claim_text"]
    assert card["source_url"] == payload["claim"]["source_url"]
    assert card["materiality"] == "UNKNOWN" and not card["impact_eligible"]
    assert card["reviewer_kind"] == "AI_SIMULATED"
    for key in [
        "claim_id",
        "review_id",
        "author_id",
        "reviewer_id",
        "uncertainties",
        "occurrence_window",
        "identity_note",
    ]:
        assert key not in card
    assert "PRIVATE" not in response.text.replace("PRIVATE_DEVELOPMENT_ONLY_NOT_APPROVAL", "")
    assert feed(client, identities, actor=2).json()["items"] == result["items"]
    assert client.get("/api/v0/news/reviewed").status_code == 401


def test_revoked_not_exposed_by_old_cutoff(client, identities, setup, enabled):
    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    old = datetime.now(UTC).isoformat()
    assert len(feed(client, identities).json()["items"]) == 1
    client.post(
        f"/api/v0/news-claims/{claim}/reviews",
        json=approval(expected_review_version=1, decision="revoked"),
        headers=headers(identities[3]),
    )
    result = feed(client, identities, as_of=old).json()
    assert result["items"] == [] and result["withheld_count"] == 1
    assert "withheld" not in result
    assert claim not in str(result)


def test_source_revision_then_correction_replaces_card(db, client, identities, setup, enabled):
    item, payload, rows = setup
    claim, body = ready(client, identities, payload)
    original = send(client, identities, claim, body).json()
    changed = deepcopy(rows)
    changed[0]["title"] += " corrected"
    with db.begin() as conn:
        save_rows(
            conn, {"id": CONFIG["id"], "config": CONFIG}, changed, "b" * 64, datetime.now(UTC)
        )
    assert feed(client, identities).json()["items"] == []
    source = client.get("/api/v0/news-claims/source/" + item, headers=headers(identities[0])).json()
    payload.update(
        revision_id=source["revision_id"], expected_payload_sha256=source["payload_sha256"]
    )
    payload["claim"].update(
        claim_text=source["text"], source_span={"start": 0, "end": len(source["text"])}
    )
    new, newbody = ready(client, identities, payload)
    newbody.update(action="correction", target_claim_id=claim)
    assert send(client, identities, new, newbody).status_code == 200
    result = feed(client, identities).json()
    assert len(result["items"]) == 1 and result["items"][0]["version"] == 2
    assert result["items"][0]["event_id"] == original["event_id"]
    with db.begin() as conn:
        conn.execute(sources.update().values(rights_status="blocked"))
    assert feed(client, identities).json()["items"] == []


def test_disabled_and_bounds(client, identities, setup, enabled, monkeypatch):
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    result = feed(client, identities).json()
    assert result["enabled"] is False and result["items"] == []
    assert feed(client, identities, limit=501).status_code == 422
    from engine.mobile_gateway import allowed

    assert allowed("GET", "/api/v0/news/reviewed")
    assert not allowed("POST", "/api/v0/news/reviewed")
    assert not allowed("GET", "/api/v0/news-claims/canonical")


def test_duplicate_one_card_and_no_projection_writes(db, client, identities, setup, enabled):
    from sqlalchemy import func

    from engine.models.schema_v15 import news_promotions

    claim, body = ready(client, identities, setup[1])
    send(client, identities, claim, body)
    other, otherbody = ready(client, identities, setup[1])
    otherbody.update(action="duplicate", target_claim_id=claim)
    send(client, identities, other, otherbody)
    assert len(feed(client, identities).json()["items"]) == 1
    assert len(feed(client, identities).json()["items"]) == 1
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(news_promotions)) == 2
