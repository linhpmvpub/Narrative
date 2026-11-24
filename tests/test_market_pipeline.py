import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from engine.local_worker_lock import worker_lock
from engine.market_discovery import discover, prioritize, profile_plan
from engine.market_pipeline import collect_due, inbox_rows
from engine.market_sources import MarketClient, validate_sec_source
from engine.models.schema_v13 import news_revisions, news_sources
from engine.news import poll, register

POLICY = json.loads(Path("config/product-v1.json").read_text())
NOW = datetime.now(UTC)
CONFIG = {
    "id": "sec_test",
    "kind": "sec_submissions",
    "name": "Synthetic SEC",
    "ticker": "NVDA",
    "cik": "0001045810",
    "url": "https://data.sec.gov/submissions/CIK0001045810.json",
    "enabled": True,
    "category": "official_filings",
    "interval_seconds": 300,
}


def submissions(**changes):
    return {
        **{
            "cik": 1045810,
            "tickers": ["NVDA"],
            "filings": {
                "recent": {
                    "accessionNumber": ["0001045810-26-000001"],
                    "filingDate": [NOW.date().isoformat()],
                    "form": ["8-K/A"],
                    "primaryDocument": ["test.htm"],
                    "reportDate": ["2026-01-01"],
                    "acceptanceDateTime": [(NOW - timedelta(minutes=1)).isoformat()],
                }
            },
        },
        **changes,
    }


def client(handler, root):
    return MarketClient(
        user_agent="Synthetic research example@example.test",
        transport=httpx.MockTransport(handler),
        capture_dir=root,
    )


def test_sec_identity_capture_and_metadata_only(tmp_path):
    c = client(lambda r: httpx.Response(200, json=submissions(), headers={"etag": "tag"}), tmp_path)
    rows, state, sha, status, _ = c.fetch(CONFIG, {}, NOW)
    assert rows[0]["is_amendment"] and rows[0]["filing_metadata_only"]
    assert rows[0]["external_id"] == "0001045810-26-000001"
    assert (tmp_path / (sha + ".json")).exists() and state["etag"] == "tag"
    c.close()
    c = client(lambda r: httpx.Response(200, json=submissions(cik=123)), tmp_path)
    with pytest.raises(ValueError, match="disagrees"):
        c.fetch(CONFIG, {}, NOW)
    c.close()


def test_sec_conditional_request_keeps_checkpoint(tmp_path):
    def handler(r):
        assert r.headers["if-none-match"] == "tag"
        return httpx.Response(304)

    c = client(handler, tmp_path)
    rows, state, sha, status, _ = c.fetch(CONFIG, {"etag": "tag"}, NOW)
    assert not rows and sha is None and state == {"etag": "tag"} and status == "NOT_MODIFIED"
    c.close()


@pytest.mark.parametrize(
    "change",
    [{"url": "https://example.test/test"}, {"cik": "1"}, {"ticker": "WDC"}, {"lookback_days": 999}],
)
def test_sec_source_scope_bounded(change):
    with pytest.raises(ValueError):
        validate_sec_source({**CONFIG, **change})


def test_sec_poll_revisions_and_source_subset(db, tmp_path):
    register(db, [CONFIG, {**CONFIG, "id": "other"}])
    c = client(lambda r: httpx.Response(200, json=submissions()), tmp_path)
    result = poll(
        db, c, now=datetime.now(UTC) + timedelta(seconds=1), source_ids=["sec_test"], max_sources=1
    )
    assert len(result) == 1 and result[0]["created"] == 1
    result = poll(db, c, now=datetime.now(UTC) + timedelta(minutes=6), source_ids=["sec_test"])
    assert result[0]["duplicates"] == 1
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(news_revisions)) == 1
        assert (
            conn.execute(
                select(news_sources.c.last_success).where(news_sources.c.id == "other")
            ).scalar()
            is None
        )
    c.close()
    with pytest.raises(ValueError):
        register(db, [{**CONFIG, "ticker": "AMD"}])


def test_failure_does_not_advance_sec_cursor(db, tmp_path):
    register(db, [CONFIG])
    c = client(lambda r: httpx.Response(429, headers={"retry-after": "900"}), tmp_path)
    assert poll(db, c, now=datetime.now(UTC) + timedelta(seconds=1))[0]["status"] == "HTTP_429"
    with db.connect() as conn:
        row = conn.execute(select(news_sources)).mappings().one()
        assert row["state"] == {} and row["failures"] == 1 and row["lease_id"] is None
    c.close()


def test_os_lock_recovers_after_owner_exit(tmp_path):
    with worker_lock(tmp_path):
        with pytest.raises(RuntimeError):
            with worker_lock(tmp_path):
                pass
    with worker_lock(tmp_path):
        pass


def test_profile_gaps_do_not_pass_for_empty_registry():
    plan = profile_plan({"items": [], "enabled": True}, POLICY)
    assert not plan["profiles_complete"] and len(plan["companies"]) == 5
    assert all(c["missing_components"] for c in plan["companies"])


def test_themes_do_not_invent_company_exposure():
    plan = profile_plan({"items": [], "enabled": True}, POLICY)
    d = discover(
        {
            "title": "Earthquake disrupts electricity supply",
            "summary": "Copper prices may increase.",
        },
        plan,
        POLICY,
    )
    assert not d["candidate_companies"] and "infrastructure" in d["families"]
    assert d["impact"] == "UNKNOWN" and not d["graph_eligible"]
    assert any("FORWARD_OR_CONDITIONAL" in s["flags"] for s in d["event_signals"])
    assert (
        "SNDK"
        not in discover({"title": "WDC HDD sales increased"}, plan, POLICY)["candidate_companies"]
    )


def test_metadata_is_not_an_extracted_event():
    plan = profile_plan({"items": [], "enabled": True}, POLICY)
    assert not discover({"title": "NVDA earnings", "filing_metadata_only": True}, plan, POLICY)[
        "event_signals"
    ]
    d = discover({"title": "AMD shipments were cancelled"}, plan, POLICY)
    assert d["candidate_companies"] == ["AMD"]
    assert "NEGATED_OR_CANCELLED" in d["event_signals"][0]["flags"]


def test_queue_diversity_dedup_and_revision_pinning():
    plan = profile_plan({"items": [], "enabled": True}, POLICY)

    def row(i, title):
        return {
            "revision_id": str(i),
            "item_id": str(i),
            "version": 2,
            "article_key": str(i),
            "source_id": "test",
            "capture_sha256": "a" * 64,
            "payload": {"title": title, "url": "https://example.test/" + str(i)},
        }

    rows = [row(i, "NVIDIA new product") for i in range(8)] + [
        row(9, "Micron capacity"),
        row(10, "Electricity prices"),
        row(10, "Electricity prices"),
    ]
    q = prioritize(rows, plan, POLICY, limit=3)
    assert len(q) == 3 and {i["revision_id"] for i in q} == {"0", "9", "10"}
    assert all(i["version"] == 2 and i["payload_sha256"] for i in q)


def test_parallel_worker_uses_each_source_once(db, tmp_path, monkeypatch):
    monkeypatch.setattr("engine.market_pipeline.time.sleep", lambda _: None)
    configs = [{**CONFIG, "id": "sec_" + str(i)} for i in range(3)]
    register(db, configs)

    def factory():
        return client(lambda r: httpx.Response(200, json=submissions()), tmp_path)

    result = collect_due(db, factory, workers=2)
    assert len(result) == 3
    assert collect_due(db, factory) == []
    rows, truncated = inbox_rows(db)
    assert len(rows) == 3 and not truncated


def test_declared_latin_feed_and_encoded_dtd_rejection():
    from engine.adapters.news import parse_feed

    text = '<?xml version="1.0" encoding="ISO-8859-1"?><rss><channel><item><title>Niño energy</title><link>https://example.test/energy</link></item></channel></rss>'
    rows, rejected = parse_feed(text.encode("latin1"), NOW)
    assert rows[0]["title"] == "Niño energy" and not rejected
    with pytest.raises(ValueError, match="DTD"):
        parse_feed('<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>'.encode("utf-16"), NOW)
    with pytest.raises(ValueError, match="Unsupported"):
        parse_feed(b'<?xml version="1.0" encoding="UTF-7"?><rss/>', NOW)


def test_operational_gate_cannot_pass_one_cycle_or_distant_receipts(tmp_path):
    from engine.ingestion.contracts import digest
    from engine.market_pipeline import save
    from engine.product_readiness import operations

    now = datetime.now(UTC)
    report = {
        "at": now.isoformat(),
        "policy_sha256": digest(POLICY),
        "poll_attempts": [{"status": "OK"}],
        "sources": [{"enabled": True, "stale": False}],
    }
    save(tmp_path / "runs" / "a.json", report)
    result = operations(tmp_path, POLICY, now=now)
    assert not result["passed"] and result["success_fraction"] == 1
    save(tmp_path / "runs" / "b.json", {**report, "at": (now - timedelta(days=8)).isoformat()})
    result = operations(tmp_path, POLICY, now=now)
    assert result["checks"]["observation_days"] and not result["checks"]["continuous_observation"]


def test_precision_bound_not_perfect_on_small_sample():
    from engine.product_readiness import wilson_lower

    assert wilson_lower(0, 0) is None
    assert 0.2 < wilson_lower(1, 1) < 0.3
    assert wilson_lower(100, 100) > 0.95


def test_extract_queue_resumes_and_holds_superseded(db, tmp_path, monkeypatch):
    from sqlalchemy import update

    from engine.ingestion.contracts import digest
    from engine.market_pipeline import extract_queue
    from engine.models.schema_v13 import news_items

    monkeypatch.setenv("NEWS_ARTICLE_DIR", str(tmp_path / "articles"))
    monkeypatch.setattr("engine.market_pipeline.time.sleep", lambda _: None)
    register(db, [CONFIG])
    c = client(lambda r: httpx.Response(200, json=submissions()), tmp_path / "feeds")
    poll(db, c)
    c.close()
    rows, _ = inbox_rows(db)
    q = prioritize(rows, profile_plan({"items": [], "enabled": True}, POLICY), POLICY)
    calls = []

    def factory():
        def handler(r):
            calls.append(str(r.url))
            return httpx.Response(
                200,
                text="<html><body>SEC synthetic filing text</body></html>",
                headers={"content-type": "text/html"},
            )

        return client(handler, tmp_path / "feeds")

    assert extract_queue(db, q, tmp_path, factory, 1)["captured"] == 1
    assert extract_queue(db, q, tmp_path, factory, 1)["already_captured"] == 1
    assert len(calls) == 1
    with db.begin() as conn:
        changed = {**rows[0]["payload"], "summary": "Corrected"}
        conn.execute(
            update(news_items).values(version=2, payload=changed, content_sha256=digest(changed))
        )
    assert extract_queue(db, q, tmp_path, factory, 1)["superseded"] == 1
    assert len(calls) == 1


def test_profile_research_checks_source_identity_and_hash(tmp_path):
    import hashlib

    from engine.market_pipeline import save
    from engine.profile_research import build

    raw = "<html><body>Our products include storage solutions. Our suppliers operate manufacturing facilities.</body></html>"
    (tmp_path / "filing.html").write_text(raw, encoding="utf-8")
    f = {
        "ticker": "SNDK",
        "cik": "0002023554",
        "form": "10-Q",
        "file": "filing.html",
        "url": "https://www.sec.gov/Archives/edgar/data/2023554/example.htm",
        "filing_date": "2026-01-01",
        "retrieved_at": NOW.isoformat(),
        "content_sha256": hashlib.sha256(raw.encode()).hexdigest(),
    }
    manifest = {"identities": {"SNDK": {"cik": "0002023554"}}, "filings": [f]}
    path = tmp_path / "collection.json"
    save(path, manifest)
    policy = {**POLICY, "tickers": ["SNDK"]}
    result = build(path, tmp_path / "drafts", policy)
    assert result["companies"][0]["sources"] == 1
    assert result["companies"][0]["sourced_components"] == 0
    draft = json.loads((tmp_path / "drafts" / "SNDK.json").read_text())
    assert draft["components"]["products"]["candidates"] and not draft["graph_eligible"]
    (tmp_path / "filing.html").write_text(raw + "changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        build(path, tmp_path / "bad", policy)
    manifest["filings"][0]["url"] = "https://www.sec.gov/Archives/edgar/data/106040/example.htm"
    save(path, manifest)
    with pytest.raises(ValueError, match="identity"):
        build(path, tmp_path / "bad", policy)


def test_discovery_coverage_distinguishes_topics_from_direct_mentions():
    from engine.market_discovery import coverage

    plan = profile_plan({"items": [], "enabled": True}, POLICY)
    plan["lexicon"].append(
        {"ticker": "NVDA", "term": "power grid", "basis": "PROFILE_TOPIC_MENTION"}
    )
    rows = [{"article_key": "x", "payload": {"title": "Power grid capacity expands"}}]
    result = coverage(rows, plan, POLICY)
    assert result["company_discovery_candidates"] == {"NVDA": 1}
    assert result["direct_company_mentions"] == {}


def test_quality_recomputes_independent_votes_and_rejects_changed_predictions(tmp_path):
    from engine.ingestion.contracts import digest
    from engine.market_pipeline import save
    from engine.product_readiness import quality

    packet = [
        {
            "id": "a",
            "cluster": "event1",
            "ticker": "NVDA",
            "profile_id": "test",
            "narrative": {"id": "demand"},
            "article": {"title": "Customer capacity expansion"},
        }
    ]
    save(tmp_path / "packet.json", packet)
    save(tmp_path / "predictions.json", {"a": False})
    save(
        tmp_path / "freeze.json",
        {
            "at": (NOW - timedelta(hours=1)).isoformat(),
            "packet_sha256": digest(packet),
            "predictions_sha256": digest({"a": False}),
            "clusters": 1,
        },
    )
    paths = []
    for reviewer in ["a", "b"]:
        path = tmp_path / (reviewer + ".json")
        save(
            path,
            {
                "packet_sha256": digest(packet),
                "reference_kind": "AI_INDEPENDENT_REVIEW",
                "reviewer_id": reviewer,
                "reviewed_at": datetime.now(UTC).isoformat(),
                "predictions_accessed": False,
                "peer_labels_accessed": False,
                "labels": [
                    {
                        "id": "a",
                        "relevance": "RELEVANT",
                        "rationale": "Named customer expansion within scope",
                    }
                ],
            },
        )
        paths.append(path)
    result = quality(tmp_path, paths, POLICY)
    assert result["metrics"]["fn"] == 1 and not result["passed"]
    assert result["clusters_per_target"] == {"MU": 0, "NVDA": 1, "AMD": 0, "DELL": 0, "SNDK": 0}
    save(tmp_path / "predictions.json", {"a": True})
    with pytest.raises(ValueError, match="Frozen artifact"):
        quality(tmp_path, paths, POLICY)
