"""Synthetic feed/API responses only; live RSS is checked separately."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select, update
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.adapters.news import FetchError, NewsClient, canonical_url, parse_feed
from engine.models.schema_v13 import news_items, news_revisions, news_sources
from engine.news import claim, poll, register

NOW = datetime.now(UTC)
CONFIG = {
    "id": "synthetic",
    "kind": "rss",
    "name": "Synthetic publisher",
    "category": "markets",
    "url": "https://publisher.example/feed",
    "interval_seconds": 60,
    "enabled": True,
}


def rss(
    title="Micron quarterly update",
    url="https://publisher.example/article?utm_source=test",
    guid="one",
):
    return f"<rss><channel><item><guid>{guid}</guid><title>{title}</title><link>{url}</link><description>&lt;b&gt;Synthetic excerpt&lt;/b&gt;</description><pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>".encode()


def test_rss_atom_normalization_and_time():
    rows, rejected = parse_feed(rss(), NOW)
    assert rejected == 0 and rows[0]["url"] == "https://publisher.example/article"
    assert rows[0]["summary"] == "Synthetic excerpt"
    atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>a</id><title>Test</title><link href="https://publisher.example/a"/><updated>2026-11-20T10:00:00Z</updated></entry></feed>'
    assert parse_feed(atom, NOW)[0][0]["external_id"] == "a"
    assert (
        canonical_url("https://publisher.example/a?id=2&amp=3&utm_x=4#x")
        == "https://publisher.example/a?amp=3&id=2"
    )


@pytest.mark.parametrize(
    "body",
    [
        b"<html>login</html>",
        b"<rss",
        '<!DOCTYPE rss [<!ENTITY x "test">]><rss/>'.encode("utf-16"),
        b'<!DOCTYPE rss [<!ENTITY x "test">]><rss/>',
        rss(url="javascript:alert(1)"),
        rss(url="http://127.0.0.1/a"),
        rss().replace(b"2026", b"2099"),
    ],
)
def test_invalid_feed_fails_closed(body):
    with pytest.raises(ValueError):
        parse_feed(body, NOW)


def test_http_conditional_auth_scope_and_no_redirects():
    def handler(request):
        assert "authorization" not in request.headers
        assert request.headers["if-none-match"] == "tag"
        return httpx.Response(304)

    c = NewsClient(token="synthetic-secret", transport=httpx.MockTransport(handler))
    assert c.fetch(CONFIG, {"etag": "tag"}, NOW)[3] == "NOT_MODIFIED"
    c.close()
    for code in (301, 401, 429, 503):
        c = NewsClient(
            transport=httpx.MockTransport(
                lambda r, code=code: httpx.Response(code, headers={"Retry-After": "600"})
            )
        )
        with pytest.raises(FetchError) as exc:
            c.fetch(CONFIG, {}, NOW)
        assert exc.value.retry == 600
        c.close()


def test_x_missing_token_and_paginated_checkpoint():
    config = {**CONFIG, "kind": "x", "handle": "ExampleFinance"}
    c = NewsClient(transport=httpx.MockTransport(lambda r: pytest.fail("No request without token")))
    with pytest.raises(FetchError) as exc:
        c.fetch(config, {}, NOW)
    assert exc.value.status == "X_NOT_CONFIGURED"
    c.close()
    calls = []

    def handler(r):
        calls.append(str(r.url))
        assert r.headers["authorization"] == "Bearer synthetic"
        if "/by/username/" in r.url.path:
            return httpx.Response(200, json={"data": {"id": "12", "username": "ExampleFinance"}})
        assert r.url.params["since_id"] == "100"
        second = "pagination_token" in r.url.params
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "101" if second else "102",
                        "author_id": "12",
                        "text": "Synthetic finance news",
                        "created_at": "2026-11-20T10:00:00Z",
                    }
                ],
                "meta": {} if second else {"next_token": "next"},
            },
        )

    c = NewsClient(token="synthetic", transport=httpx.MockTransport(handler))
    rows, state, _, _, _ = c.fetch(config, {"since_id": "100"}, NOW)
    assert len(rows) == 2 and state["since_id"] == "102" and len(calls) == 3
    c.close()


def test_x_incomplete_pagination_does_not_advance():
    c = NewsClient(
        token="synthetic",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"meta": {"next_token": "more"}})
        ),
    )
    with pytest.raises(FetchError) as exc:
        c.fetch(
            {**CONFIG, "kind": "x", "handle": "ExampleFinance"},
            {"user_id": "12", "since_id": "100"},
            NOW,
        )
    assert exc.value.status == "X_BACKLOG_EXCEEDS_PAGE_CAP"
    c.close()


def test_durable_worker_retries_versions_leases_and_cursor(db):
    register(db, [CONFIG])
    moment = datetime.now(UTC) + timedelta(seconds=1)
    body = rss()
    c = NewsClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=body, headers={"ETag": "tag"})
        )
    )
    assert poll(db, c, now=moment)[0]["created"] == 1
    assert poll(db, c, now=moment) == []
    assert poll(db, c, now=moment + timedelta(seconds=61))[0]["duplicates"] == 1
    body = rss("Micron corrected update")
    assert poll(db, c, now=moment + timedelta(seconds=122))[0]["updated"] == 1
    body = rss()
    assert poll(db, c, now=moment + timedelta(seconds=183))[0]["updated"] == 1
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(news_items)) == 1
        assert conn.scalar(select(func.count()).select_from(news_revisions)) == 3
        row = conn.execute(select(news_items)).mappings().one()
        assert row["version"] == 3 and row["payload"]["ticker_mentions"] == ["MU"]
        assert row["payload"]["graph_eligible"] is False
    held = claim(db, "synthetic", moment + timedelta(seconds=244))
    assert held and claim(db, "synthetic", moment + timedelta(seconds=244)) is None
    # A crashed lease can be recovered, including with a fresh client process.
    recovered = claim(db, "synthetic", moment + timedelta(seconds=545))
    assert recovered["lease_id"] != held["lease_id"]
    with db.begin() as conn:
        conn.execute(update(news_sources).values(lease_id=None, lease_until=None))
    bad = NewsClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(429, headers={"Retry-After": "1200"})
        )
    )
    assert poll(db, bad, now=moment + timedelta(seconds=600))[0]["status"] == "HTTP_429"
    with db.connect() as conn:
        source = conn.execute(select(news_sources)).mappings().one()
        assert source["state"]["etag"] == "tag" and source["failures"] == 1
        assert conn.scalar(select(func.count()).select_from(news_revisions)) == 3
    c.close()
    bad.close()
    with pytest.raises(ValueError, match="identity"):
        register(db, [{**CONFIG, "url": "https://other.example/feed"}])


def test_authenticated_news_inbox(client, identities, db):
    register(db, [CONFIG])
    c = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=rss())))
    poll(db, c, now=datetime.now(UTC) + timedelta(seconds=1))
    c.close()
    assert client.get("/api/v0/news").status_code == 401
    response = client.get("/api/v0/news", headers=headers(identities[0]))
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["impact"] == "UNKNOWN"
    assert client.get("/api/v0/news/sources", headers=headers(identities[0])).status_code == 200
    assert (
        client.get(
            "/api/v0/news/" + payload["items"][0]["id"] + "/history", headers=headers(identities[0])
        ).status_code
        == 200
    )
    assert client.get("/news").status_code == 200
    from engine.mobile_gateway import allowed

    assert allowed("GET", "/news") and allowed("GET", "/api/v0/news")
    assert not allowed("POST", "/api/v0/news")


def test_failure_isolated_from_other_sources_and_disabled_x(db):
    configs = [
        CONFIG,
        {**CONFIG, "id": "good", "url": "https://publisher.example/good"},
        {**CONFIG, "id": "disabled_x", "kind": "x", "handle": "ExampleFinance", "enabled": False},
    ]
    register(db, configs)

    def handler(request):
        assert request.url.host != "api.x.com"
        return httpx.Response(200, content=rss() if request.url.path == "/good" else b"<rss")

    c = NewsClient(transport=httpx.MockTransport(handler))
    result = poll(db, c, now=datetime.now(UTC) + timedelta(seconds=1))
    c.close()
    assert {r["source_id"]: r["status"] for r in result} == {
        "synthetic": "INVALID_SOURCE_RESPONSE",
        "good": "OK",
    }
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(news_items)) == 1


def test_invalid_x_identity_and_oversized_response():
    c = NewsClient(
        token="synthetic",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"data": {"id": "12", "username": "SomeoneElse"}})
        ),
    )
    with pytest.raises(ValueError, match="identity"):
        c.fetch({**CONFIG, "kind": "x", "handle": "ExampleFinance"}, {}, NOW)
    c.close()
    c = NewsClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 3_000_001))
    )
    with pytest.raises(FetchError) as exc:
        c.fetch(CONFIG, {}, NOW)
    assert exc.value.status == "RESPONSE_TOO_LARGE"
    c.close()
