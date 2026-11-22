"""Synthetic RSS/profile integration: source-bound factors, corrections and relevance."""

import hashlib
from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import select, update
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.adapters.news import parse_feed
from engine.company_profiles import FactorBinding, ProfileBundle, withdraw
from engine.models.schema_v13 import news_items, news_sources
from engine.news import register, save_rows
from engine.news_capture import archive_capture
from engine.profile_news import candidate_feed, matches


@pytest.fixture
def linked(dossier, db, monkeypatch, tmp_path):
    root, data = dossier
    now = datetime.now(UTC)
    binding = {"id": "memory", "factor_id": "f", "topic_terms": ["memory"],
        "context_terms": ["server", "servers"], "change_terms": ["prices", "costs", "supply"],
        "exclude_terms": ["memory loss"], "scope": "Synthetic input only",
        "reviewed_at": data["available_at"], "review_until": (now + timedelta(days=20)).isoformat(),
        "evidence": data["relationships"][0]["evidence"]}
    data["factor_bindings"] = [binding]
    seal(root, data)
    capture_root = tmp_path / "rss"
    monkeypatch.setenv("NEWS_CAPTURE_DIR", str(capture_root))
    config = {"id": "synthetic_a", "kind": "rss", "name": "Synthetic RSS A",
              "category": "technology", "url": "https://example.test/a.rss",
              "enabled": True, "interval_seconds": 60}
    register(db, [config])

    def insert(title="Server memory prices rise", summary="Input supply topic only.",
               source=config, age=1, archive=True):
        pub = (datetime.now(UTC) - timedelta(days=age)).isoformat()
        body = ("<rss><channel><item><guid>one</guid><link>https://example.test/news</link>"
                f"<title>{escape(title)}</title><description>{escape(summary)}</description>"
                f"<pubDate>{pub}</pubDate></item></channel></rss>").encode()
        sha = archive_capture(capture_root, body) if archive else hashlib.sha256(body).hexdigest()
        when = datetime.now(UTC)
        rows = parse_feed(body, when)[0]
        with db.begin() as conn:
            save_rows(conn, {"id": source["id"], "config": source}, rows, sha, when)
        return sha

    insert()
    return root, data, insert, config, capture_root


def get(db):
    with db.connect() as conn:
        return candidate_feed(conn)


def test_real_routing_without_ticker_or_polarity(db, linked):
    card = get(db)["items"][0]
    assert card["ticker"] == "TEST"
    assert card["stance"] == "RELATED_INFORMATION" and card["impact"] == "UNKNOWN"
    assert card["delivery"] == "disabled" and not card["graph_eligible"]
    assert card["news_revisions"][0]["capture_proof"].startswith("RAW_RSS_MATCH")
    assert len(card["links"][0]["matches"]) == 3
    for span in card["links"][0]["matches"]:
        text = card["headline"] if span["field"] == "title" else card["excerpt"]
        assert text[span["start"]:span["end"]] == span["text"]
    assert [p["id"] for p in card["links"][0]["path"]] == ["applies", "effect"]


@pytest.mark.parametrize("title", ["Memory prices rise", "Server prices rise",
                                   "Server memory overview", "Server memory loss costs",
                                   "Server memoryless prices rise"])
def test_topic_context_change_and_word_boundaries(linked, title):
    _, data, _, _, _ = linked
    binding = FactorBinding.model_validate(data["factor_bindings"][0])
    assert matches(binding, {"title": title, "summary": ""}) == []


@pytest.mark.parametrize("fault", ["profile_withdrawn", "rule_expired", "rule_disabled",
    "relation_expired", "source_disabled", "corrupt_capture", "payload_tamper", "old_news",
    "retraction"])
def test_current_validity_guards(db, linked, fault):
    root, data, insert, config, captures = linked
    if fault == "profile_withdrawn":
        withdraw(root)
    elif fault in {"rule_expired", "rule_disabled", "relation_expired"}:
        if fault == "rule_expired":
            data["factor_bindings"][0]["review_until"] = (
                datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        elif fault == "rule_disabled":
            data["factor_bindings"][0]["enabled"] = False
        else:
            data["relationships"][-1]["valid_until"] = "2025-01-01T00:00:00Z"
        seal(root, data)
    elif fault == "source_disabled":
        with db.begin() as conn:
            conn.execute(update(news_sources).values(config={**config, "enabled": False}))
    elif fault == "corrupt_capture":
        next(captures.glob("*.rss")).write_bytes(b"corrupt")
    elif fault == "payload_tamper":
        with db.begin() as conn:
            row = conn.execute(select(news_items)).mappings().one()
            conn.execute(update(news_items).values(payload={**row["payload"], "title": "Changed"}))
    elif fault == "old_news":
        insert(age=20)
    else:
        insert(summary="This article has been retracted. Server memory prices.")
    assert get(db)["items"] == []


def test_duplicate_copies_and_correction_conflict(db, linked):
    _, _, insert, config, _ = linked
    second = {**config, "id": "synthetic_b", "name": "Synthetic RSS B",
              "url": "https://example.test/b.rss"}
    register(db, [second])
    insert(source=second)
    first = get(db)["items"]
    assert len(first) == 1 and len(first[0]["news_revisions"]) == 2
    insert(title="Server memory prices corrected")
    assert get(db)["items"] == []  # Same URL but disagreeing current excerpts.
    insert(title="Server memory prices corrected", source=second)
    current = get(db)["items"][0]
    assert current["id"] == first[0]["id"]
    assert {r["version"] for r in current["news_revisions"]} == {2}
    insert(title="Unrelated new title", summary="No matched terms")
    insert(title="Unrelated new title", summary="No matched terms", source=second)
    assert get(db)["items"] == []


def test_missing_original_capture_disclosed_and_cutoff_not_backdated(db, linked):
    _, _, insert, _, _ = linked
    insert(title="Server memory costs change", archive=False)
    assert get(db)["items"][0]["news_revisions"][0]["capture_proof"] == "NOT_ARCHIVED"
    with db.connect() as conn:
        assert candidate_feed(conn, datetime(2024, 1, 1, tzinfo=UTC))["items"] == []


def test_binding_evidence_and_factor_type_required(linked):
    _, data, _, _, _ = linked
    data["factor_bindings"][0]["factor_id"] = "co"
    with pytest.raises(ValueError):
        ProfileBundle.model_validate(data)


def test_authenticated_get_only_api(client, identities, linked):
    from engine.mobile_gateway import allowed

    assert client.get("/api/v0/news/profile-rss").status_code == 401
    r = client.get("/api/v0/news/profile-rss", headers=headers(identities[0]))
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    assert "no-store" in r.headers["cache-control"]
    assert "source.html" not in r.text
    assert allowed("GET", "/api/v0/news/profile-rss")
    assert not allowed("POST", "/api/v0/news/profile-rss")
