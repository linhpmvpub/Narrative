"""Offline adversarial segment provenance and independent labeling contracts."""

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from test_development_feed import enabled as enabled
from test_financials_mobile import financial_store as financial_store
from test_product import client as client
from test_product import headers, subscribe
from test_product import identities as identities

from engine.adapters.http_sources import AcquiredDocument
from engine.development_feed import project, versions
from engine.evaluation.filing_labels import evaluate, packet
from engine.filing_evidence import assessment, ingest, parse
from engine.financials import known_filings


def claim(db):
    with db.connect() as conn:
        return next(iter(known_filings(conn, "DELL", datetime.now(UTC)).values()))


def xml(value="120", prior="100", member="dell:ISGMember", extra="", unit="iso4217:USD"):
    def ctx(i, year):
        return f"""<x:context id="c{i}"><x:entity><x:identifier scheme="http://www.sec.gov/CIK">1571996</x:identifier><x:segment><d:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">{member}</d:explicitMember>{extra}</x:segment></x:entity><x:period><x:startDate>{year}-04-01</x:startDate><x:endDate>{year}-06-30</x:endDate></x:period></x:context>"""

    return f"""<html xmlns="http://www.w3.org/1999/xhtml" xmlns:x="http://www.xbrl.org/2003/instance" xmlns:d="http://xbrl.org/2006/xbrldi" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
    {ctx(1, 2026)}{ctx(2, 2025)}<x:unit id="u"><x:measure>{unit}</x:measure></x:unit>
    <ix:nonFraction id="f1" name="us-gaap:Revenues" contextRef="c1" unitRef="u" scale="6">{value}</ix:nonFraction>
    <ix:nonFraction id="f2" name="us-gaap:Revenues" contextRef="c2" unitRef="u" scale="6">{prior}</ix:nonFraction>
    <p>ISG margin increased due to pricing and AI-optimized server mix during the quarter.</p>
    <p>ISG revenue could increase due to stronger demand but the effect remains uncertain.</p>
    <p>Revenue for the quarter is reported in the segment table and compared with the prior period.</p>
    </html>"""


def doc(c, source=None, when=None):
    source = source or xml()
    return AcquiredDocument(
        c["url"],
        source,
        when or datetime.now(UTC),
        hashlib.sha256(source.encode()).hexdigest(),
        hashlib.sha256(c["url"].encode()).hexdigest(),
    )


def test_inline_scale_context_provenance_and_causal_limits(financial_store):
    c = claim(financial_store)
    result = parse(xml(), c)
    item = result["segments"][0]
    assert item["current"]["value"] == "120000000"
    assert item["percent_change"] == "20.00"
    assert item["current"]["fact_id"] == "f1" and item["prior"]["context_id"] == "c2"
    assert item["scope"] == "reported_segment" and item["segment"] == "dell:ISGMember"
    assert item["stock_price_impact"] == "UNKNOWN"
    a, b = result["attributions"]
    assert a["status"] == "ISSUER_ATTRIBUTION" and "R028" in a["candidate_relation_ids"]
    assert b["status"] == "UNCERTAIN_OR_FORWARD_LOOKING"
    assert not a["graph_eligible"] and not a["independently_verified"]


@pytest.mark.parametrize(
    "change",
    [
        {"unit": "iso4217:EUR"},
        {"value": "NaN"},
        {"value": "1,2"},
        {
            "extra": '<d:explicitMember dimension="srt:ProductOrServiceAxis">dell:ServersMember</d:explicitMember>'
        },
        {"extra": '<d:typedMember dimension="other"><value>unknown</value></d:typedMember>'},
    ],
)
def test_ambiguous_unit_dimensions_numbers_withheld(financial_store, change):
    assert parse(xml(**change), claim(financial_store))["segments"] == []


def test_conflicts_and_entity_exclusion(financial_store):
    c = claim(financial_store)
    source = xml().replace(
        "</html>",
        '<ix:nonFraction id="f3" name="us-gaap:Revenues" contextRef="c1" unitRef="u" scale="6">999</ix:nonFraction></html>',
    )
    assert parse(source, c)["segments"] == []
    assert parse(xml().replace(">1571996<", ">99999<"), c)["segments"] == []
    assert parse(xml().replace("2025-04-01", "2025-01-01"), c)["segments"] == []
    with pytest.raises(ValueError):
        parse("<!DOCTYPE html>" + xml(), c)
    with pytest.raises(ValueError):
        parse(xml().replace('id="f2"', 'id="f1"'), c)


def test_snapshots_temporal_corrections_empty_and_hash(financial_store):
    c = claim(financial_store)
    capture = doc(c)
    assert ingest(financial_store, c, capture)["status"] == "created"
    assert ingest(financial_store, c, capture)["status"] == "duplicate"
    before = datetime.now(UTC)
    ingest(financial_store, c, doc(c, xml(value="140")))
    with financial_store.connect() as conn:
        assert (
            assessment(conn, "DELL", c["accession"], before)["segments"][0]["current"]["value"]
            == "120000000"
        )
        assert (
            assessment(conn, "DELL", c["accession"], datetime.now(UTC))["segments"][0][
                "snapshot_version"
            ]
            == 2
        )
    with pytest.raises(ValueError, match="Stale"):
        ingest(financial_store, c, capture)
    ingest(financial_store, c, doc(c, "<html/>"))
    with financial_store.connect() as conn:
        assert assessment(conn, "DELL", c["accession"], datetime.now(UTC))["segments"] == []
    bad = AcquiredDocument(
        capture.url, capture.text, datetime.now(UTC), "0" * 64, capture.url_sha256
    )
    with pytest.raises(ValueError, match="hash"):
        ingest(financial_store, c, bad)


def test_feed_map_isolation_and_disabled_edges(financial_store, client, identities):
    owner, other, _, admin = identities
    sid = subscribe(client, owner).json()["id"]
    project(financial_store, owner[0])
    c = claim(financial_store)
    before = datetime.now(UTC)
    ingest(financial_store, c, doc(c))
    feed = client.get(f"/api/v0/threads/{sid}/feed", headers=headers(owner)).json()
    assert len(feed["items"][0]["filing_evidence"]["segments"]) == 1
    graph = client.get("/api/v0/impact-map", headers=headers(owner)).json()
    assert any(n.get("observation", {}).get("scope") == "reported_segment" for n in graph["nodes"])
    assert not any(e["eligible"] for e in graph["edges"])
    assert any(e["source_matches"] for e in graph["edges"])
    assert client.get("/api/v0/impact-map", headers=headers(other)).json()["notices"] == []
    old = client.get(
        f"/api/v0/threads/{sid}/feed", headers=headers(owner), params={"as_of": before.isoformat()}
    ).json()
    assert old["items"][0]["filing_evidence"]["segments"] == []
    with financial_store.connect() as conn:
        vid = conn.scalar(select(versions.c.id))
    response = client.post(
        f"/api/v0/admin/development/versions/{vid}/lifecycle",
        headers=headers(admin),
        json={
            "expected_version": 1,
            "action": "withdrawn",
            "evidence_url": "https://www.sec.gov/synthetic-test-only",
            "reason": "Offline fabricated lifecycle regression, not a real withdrawal",
        },
    )
    assert response.status_code == 200
    graph = client.get("/api/v0/impact-map", headers=headers(owner)).json()
    assert graph["notices"][0]["filing_evidence"] == {"segments": [], "attributions": []}
    assert not any(e["source_matches"] for e in graph["edges"])


def test_blind_packet_and_no_fake_independent_labels(financial_store):
    c = claim(financial_store)
    ingest(financial_store, c, doc(c))
    with financial_store.connect() as conn:
        pack = packet(conn, datetime.now(UTC))
    assert len(pack["cases"]) == 4
    assert all(
        "status" not in case and "label" not in case and "delta" not in case
        for case in pack["cases"]
    )
    assert evaluate(pack, [])["accuracy_on_consensus"] is None
    case = next(c for c in pack["cases"] if c["kind"] == "causal_language")
    case["split"] = "holdout"  # Synthetic evaluation setup only.
    label = {
        "case_id": case["id"],
        "reviewer": "Human A",
        "independent_of_extractor": True,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "source_sha256": case["source_sha256"],
        "label": "NO_CAUSAL_CLAIM",
        "reason": "Synthetic test annotation",
    }
    assert evaluate(pack, [label])["accuracy_on_consensus"] is None
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate(pack, [label, label])
    with pytest.raises(ValueError, match="Independent"):
        evaluate(pack, [{**label, "reviewer": "codex"}])
    result = evaluate(
        pack, [label, {**label, "reviewer": "Human B", "label": "ISSUER_ATTRIBUTION"}]
    )
    assert result["disagreements"] == 1 and result["accuracy_on_consensus"] is None
