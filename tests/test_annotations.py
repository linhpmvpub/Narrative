"""Offline annotation identity, blinding, provenance and cross-source assessment checks."""

import copy
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from test_development_feed import enabled as enabled
from test_filing_evidence import claim, doc
from test_financials_mobile import financial_store as financial_store
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.annotations import import_packet
from engine.corroboration import at
from engine.corroboration import ingest as corroborate
from engine.evaluation.filing_labels import packet
from engine.filing_evidence import ingest
from engine.models.schema_v10 import labels


@pytest.fixture
def assigned(financial_store, identities):
    c = claim(financial_store)
    ingest(financial_store, c, doc(c))
    with financial_store.connect() as conn:
        pack = packet(conn, datetime.now(UTC))
    result = import_packet(financial_store, pack["cases"], [identities[0][0]])
    return result["packet_id"], pack["cases"]


def base(pid, cid):
    return f"/api/v0/annotations/{pid}/cases/{cid}"


def body(case, **changes):
    return {
        "expected_version": 0,
        "source_sha256": case["source_sha256"],
        "independent_of_extractor": True,
        "reason": "Independent synthetic annotation used in this test only",
        "language": "NO_CAUSAL_CLAIM",
        **changes,
    }


def language(cases):
    return next(c for c in cases if c["kind"] == "causal_language")


def test_assignment_and_blinding(client, identities, assigned):
    pid, cases = assigned
    owner, other, stranger, admin = identities
    assert client.get("/api/v0/annotations/packets").status_code == 401
    assert (
        client.get("/api/v0/annotations/packets", headers=headers(owner)).json()["items"][0][
            "case_count"
        ]
        == 4
    )
    assert client.get("/api/v0/annotations/packets", headers=headers(other)).json()["items"] == []
    assert (
        client.get(f"/api/v0/annotations/{pid}/cases", headers=headers(stranger)).status_code == 404
    )
    listed = client.get(f"/api/v0/annotations/{pid}/cases", headers=headers(owner)).json()["items"]
    assert len(listed) == 4 and all(item["preview"] for item in listed)
    c = language(cases)
    result = client.get(base(pid, c["id"]), headers=headers(owner)).json()
    assert result["case"] == c and result["my_label"] is None and result["my_version"] == 0
    assert set(result) == {"case", "my_label", "my_version", "source_status"}
    numeric = next(c for c in cases if c["kind"] == "segment_comparison")
    result = client.get(base(pid, numeric["id"]), headers=headers(owner)).json()
    assert not {"current", "prior", "delta", "percent_change", "prediction"} & result["case"].keys()
    assert (
        client.get(f"/api/v0/annotations/{pid}/export", headers=headers(owner)).status_code == 403
    )


def test_immutable_versions_idempotency_and_other_reviewers(
    client, financial_store, identities, assigned
):
    pid, cases = assigned
    owner, other, _, admin = identities
    c = language(cases)
    url = base(pid, c["id"]) + "/labels"
    payload = body(c)
    request_headers = headers(owner, "test-label-retry")
    first = client.post(url, headers=request_headers, json=payload)
    assert (
        first.status_code == 200
        and first.json()["version"] == 1
        and not first.json()["graph_modified"]
    )
    assert client.post(url, headers=request_headers, json=payload).json() == first.json()
    assert client.post(url, headers=headers(owner), json=payload).status_code == 409
    assert (
        client.post(
            url,
            headers=request_headers,
            json={**payload, "reason": "Changed request should conflict"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            url,
            headers=headers(owner),
            json={**payload, "expected_version": 1, "language": "ISSUER_ATTRIBUTION"},
        ).json()["version"]
        == 2
    )
    import_packet(financial_store, cases, [other[0]])
    view = client.get(base(pid, c["id"]), headers=headers(other)).json()
    assert view["my_label"] is None and view["my_version"] == 0
    assert client.post(url, headers=headers(other), json=payload).json()["version"] == 1
    revisions = client.get(f"/api/v0/annotations/{pid}/export", headers=headers(admin)).json()[
        "revisions"
    ]
    assert len(revisions) == 3 and {r["reviewer"] for r in revisions} == {owner[0], other[0]}
    assert (
        client.post(url, headers=headers(owner), json={**payload, "reviewer": other[0]}).status_code
        == 422
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"independent_of_extractor": False},
        {"reason": "          "},
        {"language": None},
        {"source_sha256": "0" * 64},
        {"numeric": {"verdict": "UNCERTAIN"}},
    ],
)
def test_invalid_label_rejected(client, identities, assigned, changes):
    pid, cases = assigned
    c = language(cases)
    response = client.post(
        base(pid, c["id"]) + "/labels", headers=headers(identities[0]), json=body(c, **changes)
    )
    assert response.status_code in {409, 422}


def test_numeric_transcription(client, identities, assigned):
    pid, cases = assigned
    c = next(c for c in cases if c["kind"] == "segment_comparison")
    data = body(c)
    data.pop("language")
    data["numeric"] = {
        "verdict": "COMPARABLE",
        "current_value": "120000000",
        "prior_value": "100000000",
        "unit": "USD",
        "current_start": "2026-04-01",
        "current_end": "2026-06-30",
        "prior_start": "2025-04-01",
        "prior_end": "2025-06-30",
    }
    url = base(pid, c["id"]) + "/labels"
    bad = copy.deepcopy(data)
    bad["numeric"]["current_value"] = "NaN"
    assert client.post(url, headers=headers(identities[0]), json=bad).status_code == 422
    bad = copy.deepcopy(data)
    bad["numeric"]["prior_start"] = "2027-01-01"
    assert client.post(url, headers=headers(identities[0]), json=bad).status_code == 422
    assert client.post(url, headers=headers(identities[0]), json=data).status_code == 200


def test_frozen_packet_tamper_and_source_revision(client, financial_store, identities, assigned):
    pid, cases = assigned
    c = language(cases)
    corrupt = copy.deepcopy(cases)
    corrupt[0]["prediction"] = "FORBIDDEN"
    with pytest.raises(ValueError, match="exactly"):
        import_packet(financial_store, corrupt, [identities[0][0]])
    current = claim(financial_store)
    ingest(financial_store, current, doc(current, "<html/>"))
    view = client.get(base(pid, c["id"]), headers=headers(identities[0])).json()
    assert view["source_status"] == "SUPERSEDED"
    assert (
        client.post(
            base(pid, c["id"]) + "/labels", headers=headers(identities[0]), json=body(c)
        ).status_code
        == 409
    )
    with financial_store.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(labels)) == 0


def dossier():
    now = datetime.now(UTC)
    return {
        "sources": [
            {
                "id": "peer",
                "url": "https://example.org/synthetic",
                "publisher": "Synthetic peer",
                "published_at": (now - timedelta(days=1)).isoformat(),
                "retrieved_at": now.isoformat(),
                "capture_sha256": hashlib.sha256(b"fixture").hexdigest(),
                "quote": "test only",
            }
        ],
        "assessments": [
            {
                "relation_id": "R028",
                "source_ids": ["peer"],
                "conclusion": "PEER_MECHANISM_ONLY",
                "limitations": ["Not Dell evidence"],
                "graph_eligible": False,
                "causal_effect_identified": False,
            }
        ],
    }


def test_corroboration_provenance_asof_and_corrections(financial_store):
    p = dossier()
    before = datetime.now(UTC)
    first = corroborate(financial_store, p, {"peer": b"fixture"})
    assert corroborate(financial_store, p, {"peer": b"fixture"})["status"] == "duplicate"
    with financial_store.connect() as conn:
        assert at(conn, before) == {}
        assert at(conn, datetime.now(UTC))["R028"]["graph_eligible"] is False
    q = copy.deepcopy(p)
    q["assessments"] = []
    corroborate(financial_store, q, {"peer": b"fixture"})
    with financial_store.connect() as conn:
        assert at(conn, datetime.now(UTC)) == {}
    assert corroborate(financial_store, p, {"peer": b"fixture"})["id"] != first["id"]
    with pytest.raises(ValueError, match="hash"):
        corroborate(financial_store, p, {"peer": b"tampered"})
    q = copy.deepcopy(p)
    q["assessments"][0]["graph_eligible"] = True
    with pytest.raises(ValueError, match="approval"):
        corroborate(financial_store, q, {"peer": b"fixture"})


def test_mobile_annotation_allowlist():
    from engine.mobile_gateway import allowed

    path = "/api/v0/annotations/" + "a" * 64 + "/cases/" + "b" * 64
    assert allowed("GET", path) and allowed("POST", path + "/labels")
    assert not allowed("POST", path) and not allowed("DELETE", path + "/labels")
    assert not allowed("GET", "/api/v0/annotations/" + "a" * 64 + "/export")
    assert not allowed("POST", "/api/v0/admin/anything")
