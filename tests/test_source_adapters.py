from datetime import UTC, datetime, timedelta

import httpx
import pytest

from engine.adapters.http_sources import (
    IRApproval,
    IRSourceAdapter,
    SECSourceAdapter,
    SourceClient,
    SourceUnavailable,
)

NOW = datetime(2026, 11, 19, tzinfo=UTC)


class FakeTime:
    value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, duration):
        self.value += duration


def source_client(handler, tmp_path=None):
    clock = FakeTime()
    client = SourceClient(
        user_agent="Threadnote tests tester@example.invalid",
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        now=lambda: NOW,
    )
    return client, clock


def test_sec_retry_throttle_hash_cache_and_replay(tmp_path):
    calls = []

    def handler(request):
        calls.append((request, clock.value))
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"cik": "0000000001", "filings": {}, "facts": {}})

    client, clock = source_client(handler, tmp_path)
    sec = SECSourceAdapter(client)
    document = sec.submissions("1")
    assert len(document.content_sha256) == len(document.url_sha256) == 64
    assert calls[0][0].headers["User-Agent"].startswith("Threadnote tests")
    assert str(calls[0][0].url).endswith("submissions/CIK0000000001.json")
    assert calls[1][1] - calls[0][1] >= 0.5
    assert sec.submissions("1") == document
    assert len(calls) == 2
    sec.companyfacts("1")
    assert calls[-1][1] - calls[-2][1] >= 0.5
    with pytest.raises(SourceUnavailable, match="as_of"):
        sec.submissions("1", as_of=NOW - timedelta(days=1))
    assert len(calls) == 3
    client.close()
    replay, _ = source_client(lambda _: pytest.fail("Replay must not fetch"), tmp_path)
    assert SECSourceAdapter(replay).submissions("1", as_of=NOW) == document
    replay.close()


@pytest.mark.parametrize("status", [403, 404, 500, 302])
def test_sec_error_never_fabricates_data(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://unapproved.invalid"})

    client, _ = source_client(handler)
    with pytest.raises(SourceUnavailable):
        SECSourceAdapter(client).submissions("1")
    assert len(calls) == (4 if status == 500 else 1)
    assert client.snapshots == []
    client.close()


@pytest.mark.parametrize("payload", [{"cik": 2, "filings": {}}, {"cik": 1}, [1, 2]])
def test_sec_invalid_or_wrong_issuer(payload):
    client, _ = source_client(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(SourceUnavailable):
        SECSourceAdapter(client).submissions("1")
    client.close()


def test_timeout_exhausts_budget():
    def handler(request):
        raise httpx.ReadTimeout("test", request=request)

    client, clock = source_client(handler)
    with pytest.raises(SourceUnavailable):
        SECSourceAdapter(client).companyfacts("1")
    assert clock.value >= 15
    client.close()


@pytest.mark.parametrize("status", ["pending", "blocked"])
def test_ir_rights_fail_before_network(status):
    client, _ = source_client(lambda _: pytest.fail("Must not fetch"))
    approval = IRApproval("https://ir.example.invalid", status, "reviewer", "test rights", NOW)
    with pytest.raises(ValueError):
        IRSourceAdapter(client, [approval]).fetch("https://ir.example.invalid/release")
    client.close()


def test_ir_exact_origin_and_approval_time():
    client, _ = source_client(lambda _: httpx.Response(200, text="Test release"))
    ir = IRSourceAdapter(
        client,
        [IRApproval("https://ir.example.invalid", "approved", "reviewer", "test rights", NOW)],
    )
    for url in (
        "https://ir.example.invalid.evil.invalid/release",
        "http://ir.example.invalid/release",
        "https://user@ir.example.invalid/release",
    ):
        with pytest.raises(ValueError):
            ir.fetch(url)
    with pytest.raises(ValueError):
        ir.fetch("https://ir.example.invalid/release", as_of=NOW - timedelta(days=1))
    assert ir.fetch("https://ir.example.invalid/release").text == "Test release"
    client.close()


def test_bounded_body_and_invalid_cik():
    client, _ = source_client(lambda _: httpx.Response(200, content=b"x" * 5_000_001))
    sec = SECSourceAdapter(client)
    with pytest.raises(ValueError):
        sec.submissions("../secret")
    with pytest.raises(SourceUnavailable, match="5MB"):
        sec.submissions("1")
    client.close()
