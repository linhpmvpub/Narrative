"""Synthetic grouping and temporal provenance checks; no market truth labels."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_news import CONFIG, rss
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.ingestion.contracts import digest
from engine.news import register, save_rows
from engine.news_clusters import analyze, build, publisher

NOW = datetime(2026, 1, 10, tzinfo=UTC)
TITLE = "Nvidia reports quarterly revenue growth driven by enterprise demand"


def row(id, *, title=TITLE, url=None, tickers=None, days=0):
    return {
        "id": "revision-" + id,
        "item_id": id,
        "version": 1,
        "capture_sha256": digest(id),
        "received_at": NOW,
        "payload": {
            "title": title,
            "url": url or f"https://www.cnbc.com/{id}",
            "ticker_mentions": tickers if tickers is not None else ["NVDA"],
            "published_at": (NOW + timedelta(days=days)).isoformat(),
        },
    }


def test_duplicate_feed_urls_and_publisher_groups_are_not_independent_votes():
    rows = [
        row("a"),
        row("b", url="https://www.cnbc.com/a?utm_source=duplicate"),
        row("c", url="https://www.marketwatch.com/article/c"),
    ]
    result = build(rows, NOW)
    group = result["items"][0]
    assert result["cluster_count"] == 1 and group["member_count"] == 3
    assert group["unique_articles"] == 2 and group["publisher_group_count"] == 2
    assert group["reporting_independence"] == "NOT_ESTABLISHED"
    assert not group["claim_verified"] and not group["impact_handoff"]["ready"]
    assert not group["impact_handoff"]["graph_eligible"]
    assert publisher("https://x.com/CNBC/status/1")[0] == publisher("https://cnbc.com/a")[0]
    assert publisher("https://evilcnbc.com/a")[0] == "unknown"


@pytest.mark.parametrize("change", ["company", "time", "missing_time", "different_story"])
def test_similar_topic_is_not_sufficient(change):
    a, b = row("a"), row("b")
    if change == "company":
        b["payload"]["ticker_mentions"] = ["MU"]
    if change == "time":
        b["payload"]["published_at"] = (NOW + timedelta(days=4)).isoformat()
    if change == "missing_time":
        b["payload"]["published_at"] = None
    if change == "different_story":
        b["payload"]["title"] = "Nvidia faces new antitrust lawsuit in federal court"
    assert build([a, b], NOW)["cluster_count"] == 2


def test_complete_link_prevents_similarity_chain_and_is_order_stable():
    rows = [
        row("a", title="alpha beta gamma delta epsilon zeta", tickers=[]),
        row("b", title="alpha beta gamma delta epsilon zeta theta", tickers=[]),
        row("c", title="alpha beta gamma delta epsilon zeta theta omega", tickers=[]),
    ]
    result = build(rows, NOW)
    assert result["cluster_count"] == 2
    assert build(list(reversed(rows)), NOW) == result


def test_numeric_direction_differences_are_review_flags_not_truth():
    a = row("a", title="Nvidia quarterly revenue increased to 20 billion from enterprise demand")
    b = row(
        "b",
        title="Nvidia quarterly revenue decreased to 30 billion from enterprise demand",
        url="https://marketwatch.com/b",
    )
    result = build([a, b], NOW)
    assert result["cluster_count"] == 1
    group = result["items"][0]
    assert len(group["potential_conflicts"]) == 2
    assert group["impact_handoff"]["priority"] == "CONFLICT_REVIEW"
    assert "POTENTIAL_CONFLICT_REQUIRES_REVIEW" in group["impact_handoff"]["blockers"]


def test_revision_changes_snapshot_identity_without_mutating_inputs():
    original = [row("a"), row("b")]
    before = deepcopy(original)
    first = build(original, NOW)
    assert original == before
    original[0]["version"] = 2
    original[0]["id"] = "new-revision"
    assert build(original, NOW)["snapshot_sha256"] != first["snapshot_sha256"]
    unknown = build([row("z", url="https://unknown.example/a", tickers=[])], NOW)["items"][0]
    assert unknown["publisher_group_count"] == 0
    assert "NO_RESOLVED_PILOT_COMPANY" in unknown["impact_handoff"]["blockers"]


def test_asof_replays_revision_and_excludes_later_corrections(db, client, identities):
    from engine.adapters.news import parse_feed

    register(db, [CONFIG])
    first = parse_feed(rss(), datetime.now(UTC))[0]
    first[0]["published_at"] = NOW.isoformat()
    source = {"id": CONFIG["id"], "config": CONFIG}
    with db.begin() as conn:
        save_rows(conn, source, first, "a" * 64, NOW)
        revised = deepcopy(first)
        revised[0]["title"] = "Micron faces a separate legal investigation"
        save_rows(conn, source, revised, "b" * 64, NOW + timedelta(days=1))
    old = analyze(db, NOW + timedelta(hours=1))
    newer = analyze(db, NOW + timedelta(days=2))
    assert old["items"][0]["members"][0]["version"] == 1
    assert newer["items"][0]["members"][0]["version"] == 2
    assert old["snapshot_sha256"] != newer["snapshot_sha256"]
    assert client.get("/api/v0/news/clusters").status_code == 401
    result = client.get("/api/v0/news/clusters", headers=headers(identities[0]))
    assert result.status_code == 200 and result.json()["canonical_events_created"] == 0
    with pytest.raises(ValueError):
        analyze(db, datetime.now())
    with pytest.raises(ValueError):
        analyze(db, datetime.now(UTC) + timedelta(days=1))
    from engine.mobile_gateway import allowed

    assert allowed("GET", "/api/v0/news/clusters")
    assert not allowed("POST", "/api/v0/news/clusters")
