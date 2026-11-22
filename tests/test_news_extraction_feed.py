"""Unverified feed stays separate, current and private; no approval inferred."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from test_news import CONFIG, rss
from test_news_ingestion import enabled as enabled
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.adapters.news import NewsClient, parse_feed
from engine.models.schema_v13 import news_revisions
from engine.news import register, save_rows
from engine.news_articles import capture, root_dir


@pytest.fixture
def extraction(db, client, identities, enabled, tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_ARTICLE_DIR", str(tmp_path))
    register(db, [CONFIG])
    rows = parse_feed(rss(url="https://nvidianews.nvidia.com/test"), datetime.now(UTC))[0]
    with db.begin() as conn:
        save_rows(
            conn,
            {"id": CONFIG["id"], "config": CONFIG},
            rows,
            "a" * 64,
            datetime.now(UTC) - timedelta(seconds=10),
        )
        revision = conn.execute(select(news_revisions)).mappings().one()
    table = b"<p>GAAP</p><p>($ in billions, except earnings per share)</p><p>Q3 FY27</p><p>Q2 FY27</p><p>Q3 FY26</p><p>Q/Q*</p><p>Y/Y*</p><p>Revenue</p><p>$100</p><p>$90</p><p>$80</p>"
    c = NewsClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=table, headers={"content-type": "text/html"})
        )
    )
    try:
        result = capture(revision, c)
        capture(revision, c)
    finally:
        c.close()
    return result, rows


def test_extraction_member_feed_and_corruption(client, identities, extraction):
    assert client.get("/api/v0/news/extractions").status_code == 401
    r = client.get("/api/v0/news/extractions", headers=headers(identities[0]))
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["status"] == "UNVERIFIED_EXTRACTION" and not item["impact_eligible"]
    assert item["currency"] == "UNKNOWN" and item["period_normalization"] == "UNRESOLVED"
    assert "revision_id" not in item and "packet_sha256" not in item
    assert "no-store" in r.headers["cache-control"]
    result, _ = extraction
    (root_dir() / "bodies" / (result["body_sha256"] + ".html")).write_bytes(b"corrupt")
    assert (
        client.get("/api/v0/news/extractions", headers=headers(identities[0])).json()["items"] == []
    )
    from engine.mobile_gateway import allowed

    assert allowed("GET", "/api/v0/news/extractions")
    assert not allowed("POST", "/api/v0/news/extractions")


def test_extraction_source_edit_withholds_without_fallback(db, client, identities, extraction):
    _, rows = extraction
    rows[0]["title"] = "Micron corrected source"
    with db.begin() as conn:
        save_rows(conn, {"id": CONFIG["id"], "config": CONFIG}, rows, "b" * 64, datetime.now(UTC))
    assert (
        client.get("/api/v0/news/extractions", headers=headers(identities[0])).json()["items"] == []
    )


def test_extraction_explicit_source_block(db, client, identities, extraction):
    from engine.ingestion.reviewed import sources

    result, _ = extraction
    with db.begin() as conn:
        conn.execute(
            sources.insert().values(
                id="news-reviewed:" + result["revision_id"],
                name="Synthetic blocked source",
                origin="web",
                rights_status="blocked",
                citation_url=result["url"],
                created_at=datetime.now(UTC),
            )
        )
    response = client.get("/api/v0/news/extractions", headers=headers(identities[0]))
    assert response.json()["items"] == []
