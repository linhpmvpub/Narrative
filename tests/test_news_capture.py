"""Capture integrity and cursor safety using synthetic source bodies."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from test_news import CONFIG, rss

from engine.adapters.news import NewsClient
from engine.models.schema_v13 import news_revisions, news_sources
from engine.news import poll, register
from engine.news_capture import LIMIT, archive_capture, read_capture


def test_atomic_deduplicated_capture_and_tamper(tmp_path):
    body = rss()
    with ThreadPoolExecutor(max_workers=4) as pool:
        hashes = list(pool.map(lambda _: archive_capture(tmp_path, body), range(8)))
    assert len(set(hashes)) == 1
    assert read_capture(tmp_path, hashes[0]) == body
    assert len(list(tmp_path.iterdir())) == 1
    (tmp_path / (hashes[0] + ".rss")).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="integrity"):
        archive_capture(tmp_path, body)
    assert len(list(tmp_path.iterdir())) == 1


def test_capture_bounds_and_missing_history(tmp_path):
    with pytest.raises(ValueError, match="hash"):
        read_capture(tmp_path, "../private")
    with pytest.raises(FileNotFoundError):
        read_capture(tmp_path, "0" * 64)
    with pytest.raises(ValueError, match="limit"):
        archive_capture(tmp_path, b"x" * (LIMIT + 1))
    assert list(tmp_path.iterdir()) == []


def test_worker_capture_revision_and_fail_closed_cursor(db, tmp_path):
    register(db, [CONFIG])
    moment = datetime.now(UTC) + timedelta(seconds=1)
    body = rss()
    client = NewsClient(
        capture_dir=tmp_path,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=body, headers={"etag": "first"})
        ),
    )
    try:
        assert poll(db, client, now=moment)[0]["created"] == 1
        with db.connect() as conn:
            revision = conn.execute(select(news_revisions)).mappings().one()
        assert read_capture(tmp_path, revision["capture_sha256"]) == body
        body = rss("Micron correction")
        sha = hashlib.sha256(body).hexdigest()
        (tmp_path / (sha + ".rss")).write_bytes(b"corrupted")
        assert poll(db, client, now=moment + timedelta(seconds=61))[0]["status"] == (
            "CAPTURE_ARCHIVE_FAILED"
        )
        with db.connect() as conn:
            source = conn.execute(select(news_sources)).mappings().one()
            assert source["state"] == {"etag": "first", "modified": None}
            assert source["failures"] == 1
            assert len(conn.execute(select(news_revisions)).all()) == 1
    finally:
        client.close()


def test_invalid_response_archived_and_304_not_fabricated(tmp_path):
    body = b"<broken"
    client = NewsClient(
        capture_dir=tmp_path,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)),
    )
    try:
        with pytest.raises(ValueError):
            client.fetch(CONFIG, {}, datetime.now(UTC))
        assert read_capture(tmp_path, hashlib.sha256(body).hexdigest()) == body
    finally:
        client.close()
    before = set(tmp_path.iterdir())
    client = NewsClient(
        capture_dir=tmp_path, transport=httpx.MockTransport(lambda r: httpx.Response(304))
    )
    try:
        assert client.fetch(CONFIG, {"etag": "old"}, datetime.now(UTC))[3] == "NOT_MODIFIED"
        assert set(tmp_path.iterdir()) == before
    finally:
        client.close()
