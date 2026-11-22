"""Dossier availability, current validity, and no automatic causal promotion."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

from test_news_claims import setup as setup
from test_news_ingestion import enabled as enabled
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.ingestion.contracts import digest


def request(client, identities, setup, actor=3, **changes):
    return client.get(
        "/api/v0/news-claims/source/" + setup[0] + "/dossier",
        params={
            "ticker": "MU",
            "expected_payload_sha256": setup[1]["expected_payload_sha256"],
            **changes,
        },
        headers=headers(identities[actor]),
    )


def test_dossier_missing_context_and_roles(client, identities, setup, enabled):
    response = request(client, identities, setup)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["financial_context"] == [] and result["segment_context"] == []
    assert result["materiality"] == "UNKNOWN" and not result["impact_eligible"]
    assert result["source"]["payload_sha256"] == setup[1]["expected_payload_sha256"]
    sha = result.pop("dossier_sha256")
    assert digest(result) == sha
    assert request(client, identities, setup, actor=0).status_code == 403
    assert request(client, identities, setup, ticker="NVDA").status_code == 409
    assert request(client, identities, setup, ticker="WDC").status_code == 409
    assert request(client, identities, setup, expected_payload_sha256="0" * 64).status_code == 409
    from engine.mobile_gateway import allowed

    assert not allowed("GET", "/api/v0/news-claims/source/" + setup[0] + "/dossier")


def test_context_cutoff_and_no_causal_inference(client, identities, setup, enabled, monkeypatch):
    import engine.news_dossier as module

    times = []
    comparison = {
        "snapshot_id": "s1",
        "accession": "a1",
        "metric": "REVENUE",
        "current": {"end": "2026-09-30"},
    }

    def comparisons(conn, ticker, cutoff):
        assert ticker == "MU"
        times.append(cutoff)
        return [deepcopy(comparison)]

    monkeypatch.setattr(module, "assessments", comparisons)
    monkeypatch.setattr(
        module,
        "known_filings",
        lambda *args: {"a1": {"filing_date": "2026-10-01", "source_status": "active"}},
    )
    monkeypatch.setattr(
        module,
        "assessment",
        lambda *args: {
            "segments": [{"snapshot_id": "seg1", "source_url": "https://www.sec.gov/example"}]
        },
    )
    result = request(client, identities, setup).json()
    assert times[0] == datetime.fromisoformat(result["source"]["captured_at"])
    assert times[0] < times[1]
    assert len(result["financial_context"]) == 1 and len(result["segment_context"]) == 1
    assert result["exposure"] == "UNKNOWN" and result["causal_attribution"] == "NOT_ESTABLISHED"
    assert "NEWS_TO_FINANCIAL_METRIC_LINK_UNVERIFIED" in result["blockers"]


def test_superseded_financial_and_segment_context_removed(
    client, identities, setup, enabled, monkeypatch
):
    import engine.news_dossier as module

    threshold = datetime.now(UTC) - timedelta(seconds=10)
    monkeypatch.setattr(
        module,
        "assessments",
        lambda conn, ticker, at: [
            {
                "snapshot_id": "old" if at < threshold else "new",
                "accession": "a1",
                "metric": "REVENUE",
                "current": {"end": "2026-09-30"},
            }
        ],
    )
    monkeypatch.setattr(
        module, "known_filings", lambda *args: {"a1": {"filing_date": "2026-10-01"}}
    )
    monkeypatch.setattr(
        module,
        "assessment",
        lambda conn, ticker, accession, at: {
            "segments": [{"snapshot_id": "old" if at < threshold else "new"}]
        },
    )
    result = request(client, identities, setup).json()
    assert result["financial_context"] == [] and result["segment_context"] == []


def test_dossier_rejects_changed_source_and_disabled_mode(
    db, client, identities, setup, enabled, monkeypatch
):
    from engine.models.schema_v13 import news_items

    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "false")
    assert request(client, identities, setup).status_code == 409
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "true")
    with db.begin() as conn:
        conn.execute(
            news_items.update()
            .where(news_items.c.id == setup[0])
            .values(payload={"title": "changed"})
        )
    assert request(client, identities, setup).status_code == 409
