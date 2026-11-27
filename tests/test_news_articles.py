"""Synthetic article and financial worksheet evidence, no real approval."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from engine.adapters.news import FetchError, NewsClient
from engine.news_articles import capture, evidence, read_packet, root_dir
from engine.news_measurements import Worksheet, evaluate

HTML = b"<html><script>secret instruction</script><p>NVIDIA</p><p>Revenue</p><p>consolidated</p><p>GAAP</p><p>three months</p><p>USD</p><p>millions</p><p>Q3 FY2027</p><p>100</p><p>Q3 FY2026</p><p>80</p></html>"


@pytest.fixture
def packet(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_ARTICLE_DIR", str(tmp_path))
    revision = {
        "id": "synthetic-revision",
        "received_at": datetime.now(UTC) - timedelta(days=1),
        "payload": {"url": "https://nvidianews.nvidia.com/test"},
    }
    c = NewsClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
        )
    )
    try:
        saved = capture(revision, c)
    finally:
        c.close()
    return revision, saved


def test_article_integrity_roles_and_no_backdating(packet):
    revision, saved = packet
    manifest, text = read_packet(revision, saved["packet_sha256"])
    assert "secret instruction" not in text
    assert datetime.fromisoformat(manifest["retrieved_at"]) > revision["received_at"]
    assert evidence(revision)["items"][0]["status"] == "INTEGRITY_CHECKED_UNREVIEWED"
    assert not evidence(revision)["independent_corroboration"]
    changed = deepcopy(revision)
    changed["payload"]["title"] = "changed"
    with pytest.raises(ValueError, match="revision"):
        read_packet(changed, saved["packet_sha256"])
    (root_dir() / "bodies" / (manifest["body_sha256"] + ".html")).write_bytes(b"tampered")
    assert evidence(revision)["items"][0]["status"] == "INVALID_OR_UNAVAILABLE"


@pytest.mark.parametrize("host", ["micron.gcs-web.com", "www.sandisk.com"])
def test_public_issuer_capture_is_local_unreviewed_and_exact_host(tmp_path, host):
    revision = {"id": "synthetic-issuer", "received_at": datetime.now(UTC),
                "payload": {"url": f"https://{host}/synthetic-release"}}
    c = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(
        200, content=HTML, headers={"content-type": "text/html"})))
    try:
        saved = capture(revision, c, root=tmp_path)
        checked, text = read_packet(revision, saved["packet_sha256"], root=tmp_path)
        assert text and not checked["impact_eligible"]
        assert checked["review_status"] == "UNREVIEWED"
        with pytest.raises(ValueError, match="allowlisted"):
            capture(revision, c, root=tmp_path, url=f"https://{host}.example.org/a",
                    relation="issuer_context")
    finally:
        c.close()


@pytest.mark.parametrize("code", [302, 403, 429])
def test_article_no_redirect_or_access_bypass(packet, code):
    revision, _ = packet
    c = NewsClient(transport=httpx.MockTransport(lambda r: httpx.Response(code)))
    try:
        with pytest.raises(FetchError):
            capture(revision, c)
        with pytest.raises(ValueError, match="allowlisted"):
            capture(revision, c, url="https://private.example/a", relation="issuer_context")
        with pytest.raises(ValueError, match="exactly"):
            capture(revision, c, url="https://www.cnbc.com/other")
    finally:
        c.close()


def worksheet(revision, saved):
    _, text = read_packet(revision, saved["packet_sha256"])

    def span(value):
        start = text.index(value)
        return {"start": start, "end": start + len(value)}

    def operand(value, period):
        return {
            k: span(v)
            for k, v in {
                "value": value,
                "period": period,
                "unit": "USD",
                "scale": "millions",
                "concept": "Revenue",
                "scope": "consolidated",
                "accounting_basis": "GAAP",
                "duration": "three months",
            }.items()
        }

    return {
        "packet_sha256": saved["packet_sha256"],
        "ticker": "NVDA",
        "issuer": span("NVIDIA"),
        "current": operand("100", "Q3 FY2027"),
        "prior": operand("80", "Q3 FY2026"),
        "limitations": "Synthetic example only; requires independent financial review.",
    }


def test_source_span_financial_scale_and_comparison(packet):
    revision, saved = packet
    data = worksheet(revision, saved)
    result = evaluate(revision, Worksheet.model_validate(data))
    assert result["current"]["scaled_value"] == "100000000"
    assert result["arithmetic_change_percent"] == "25.0000"
    assert not result["impact_eligible"]
    data["prior"]["period"] = data["current"]["period"]
    with pytest.raises(ValueError, match="Distinct"):
        evaluate(revision, Worksheet.model_validate(data))


def test_financial_wrong_issuer_units_and_span(packet):
    revision, saved = packet
    for mutation, match in [("issuer", "Issuer"), ("unit", "currency"), ("span", "exceeds")]:
        data = worksheet(revision, saved)
        if mutation == "issuer":
            data["ticker"] = "MU"
        if mutation == "unit":
            data["current"]["unit"] = data["current"]["concept"]
        if mutation == "span":
            data["current"]["value"] = {"start": 0, "end": 99999}
        with pytest.raises(ValueError, match=match):
            evaluate(revision, Worksheet.model_validate(data))


def test_explicit_table_candidates_preserve_unresolved_fields(packet):
    from engine.news_articles import capture
    from engine.news_numeric_candidates import candidates

    revision, _ = packet
    table = b"<p>GAAP</p><p>($ in billions, except earnings per share)</p><p>Q3 FY27</p><p>Q2 FY27</p><p>Q3 FY26</p><p>Q/Q*</p><p>Y/Y*</p><p>Revenue</p><p>$100.0</p><p>$90.0</p><p>$80.0</p>"
    c = NewsClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=table, headers={"content-type": "text/html"})
        )
    )
    try:
        saved = capture(revision, c)
    finally:
        c.close()
    result = candidates(revision, saved["packet_sha256"])
    row = result["items"][0]
    assert row["fields"]["current"]["quote"] == "Q3 FY27"
    assert row["fields"]["prior_value"]["quote"] == "80.0"
    assert row["currency"] == "UNKNOWN" and row["period_normalization"] == "UNRESOLVED"
    assert not row["impact_eligible"]
    _, text = read_packet(revision, saved["packet_sha256"])
    for field in row["fields"].values():
        assert text[field["start"] : field["end"]] == field["quote"]
