"""Synthetic SEC metadata and source-integrity checks for offline held corpora."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal as seal_profile

from engine.collect_sec import TICKERS
from engine.evaluation.held_role_corpus import Links, audit, evaluate, prepare
from engine.ingestion.contracts import digest


@pytest.fixture
def corpus(tmp_path):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    source = tmp_path / "sources"
    source.mkdir()
    cik = "0000000001"
    accession = "0000000001-26-000001"
    payload = {"cik": 1, "tickers": ["MU"], "filings": {"recent": {
        "accessionNumber": [accession], "filingDate": ["2026-01-02"],
        "reportDate": ["2025-12-31"], "form": ["10-K"],
        "primaryDocument": ["filing.htm"]}}}
    index = {str(i): {"ticker": t, "cik_str": i + 1, "title": t}
             for i, t in enumerate(TICKERS)}

    def save(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {"index_sha256": save(metadata / "company_tickers.json", index),
        "identities": {"MU": {"cik": cik, "submission_sha256": save(
            metadata / "MU-submissions.json", payload)}}}
    save(metadata / "collection.json", manifest)
    raw = ("<p>Our suppliers manufacture memory components used in systems. Delivery delays "
           "can affect capacity and prevent us from meeting our customers' requirements "
           "under existing supply agreements and purchase commitments.</p>")
    (source / "filing.html").write_text(raw, encoding="utf-8")
    filing = {"ticker": "MU", "cik": cik, "accession": accession, "form": "10-K",
        "filing_date": "2026-01-02", "url":
        "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/filing.htm",
        "file": "filing.html", "collection_directory": "sources",
        "content_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "retrieved_at": "2026-02-01T00:00:00+00:00",
        "first_available_to_engine_at": "2026-02-01T00:00:00+00:00"}
    index_path = tmp_path / "held.json"
    save(index_path, {"filings": [filing]})
    return tmp_path, metadata, index_path, payload, manifest, filing, save


def test_eligible_issuer_period_and_exact_bytes(corpus):
    root, metadata, index, *_ = corpus
    rows = audit(index, metadata, root)
    assert rows[0]["status"] == "ELIGIBLE_TEXT_CHALLENGE_ONLY"
    assert rows[0]["source"]["cluster_key"] == "0000000001:2025-12-31"
    assert "Our suppliers" in rows[0]["raw"]


@pytest.mark.parametrize("fault", ["hash", "escape", "clock", "identity", "metadata"])
def test_fail_closed_on_corrupt_provenance(corpus, fault):
    root, metadata, index, payload, manifest, filing, save = corpus
    if fault == "hash":
        (root / "sources/filing.html").write_text("modified")
    elif fault == "escape":
        filing["collection_directory"] = "../outside"
    elif fault == "clock":
        filing["first_available_to_engine_at"] = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    elif fault == "identity":
        filing["cik"] = "0000009999"
    else:
        (metadata / "MU-submissions.json").write_text("{}")
    save(index, {"filings": [filing]})
    with pytest.raises(ValueError):
        audit(index, metadata, root)


def test_original_and_amendment_family_withheld(corpus):
    root, metadata, index, payload, manifest, filing, save = corpus
    recent = payload["filings"]["recent"]
    for values in recent.values():
        values.append(values[0])
    recent["accessionNumber"][1] = "0000000001-26-000002"
    recent["form"][1] = "10-K/A"
    recent["primaryDocument"][1] = "amendment.htm"
    manifest["identities"]["MU"]["submission_sha256"] = save(
        metadata / "MU-submissions.json", payload)
    save(metadata / "collection.json", manifest)
    rows = audit(index, metadata, root)
    assert rows[0]["status"] == "AMENDMENT_FAMILY_REVIEW_REQUIRED"
    result = prepare(index, metadata, root, root / "out")
    assert result["selected_clusters"] == 0
    assert not (root / "out/predictions.json").exists()


def test_8k_not_mislabeled_as_negative_without_exhibits(corpus):
    root, metadata, index, payload, manifest, filing, save = corpus
    filing["form"] = payload["filings"]["recent"]["form"][0] = "8-K"
    manifest["identities"]["MU"]["submission_sha256"] = save(
        metadata / "MU-submissions.json", payload)
    save(metadata / "collection.json", manifest)
    save(index, {"filings": [filing]})
    assert audit(index, metadata, root)[0]["status"] == "EVENT_AND_EXHIBIT_REVIEW_REQUIRED"


def test_exhibit_links_confined_to_accession():
    links = Links("https://www.sec.gov/Archives/edgar/data/1/123/main.htm")
    links.feed('<a href="ex99.htm#part">Exhibit</a><a href="ex99.htm">duplicate</a>'
               '<a href="../other/ex.htm">elsewhere</a><a href="https://evil.test/ex.htm">bad</a>'
               '<a href="#item">same</a><a href="javascript:alert(1)">bad</a>')
    assert links.links == {"https://www.sec.gov/Archives/edgar/data/1/123/ex99.htm"}


def test_legacy_newlines_keep_physical_and_content_hashes(corpus):
    root, metadata, index, _, _, filing, save = corpus
    path = root / "sources/filing.html"
    raw = path.read_bytes() + b"\n"
    filing["content_sha256"] = hashlib.sha256(raw).hexdigest()
    path.write_bytes(raw.replace(b"\n", b"\r\n"))
    save(index, {"filings": [filing]})
    source = audit(index, metadata, root)[0]["source"]
    assert source["stored_bytes_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert source["stored_bytes_sha256"] != source["source_sha256"]


def test_duplicate_document_not_an_independent_cluster(corpus):
    root, metadata, index, _, _, filing, save = corpus
    save(index, {"filings": [filing, filing]})
    rows = audit(index, metadata, root)
    assert [r["status"] for r in rows] == ["ELIGIBLE_TEXT_CHALLENGE_ONLY", "DUPLICATE_DOCUMENT"]


def test_previously_reviewed_document_excluded_and_frozen_output_preserved(corpus):
    root, metadata, index, _, _, filing, save = corpus
    prior = root / "prior"
    prior.mkdir()
    packet = [{"archive_source": {"source_sha256": filing["content_sha256"]},
               "article": {"summary": "A different excerpt"}}]
    save(prior / "packet.json", packet)
    save(prior / "freeze.json", {"packet_sha256": digest(packet)})
    out = root / "out"
    report = prepare(index, metadata, root, out, [prior / "packet.json"])
    assert report["disposition"] == {"PREVIOUSLY_REVIEWED_DOCUMENT": 1}
    with pytest.raises(ValueError, match="Output exists"):
        prepare(index, metadata, root, out)


def test_freeze_counts_exclusions_and_checks_audit_integrity(corpus, dossier, monkeypatch):
    root, metadata, index, _, _, filing, save = corpus
    profile_root, data = dossier
    data["factor_bindings"] = [{"id": "test", "factor_id": "f",
        "topic_terms": ["suppliers"], "context_terms": ["capacity"], "change_terms": ["delays"],
        "scope": "Synthetic", "reviewed_at": data["available_at"],
        "review_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "evidence": data["relationships"][0]["evidence"]}]
    seal_profile(profile_root, data)
    registry = root / "profiles"
    registry.mkdir()
    profile_root.rename(registry / "example")
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(registry))
    repeated = ("The unrelated accounting discussion describes a change in the treatment of "
                "administrative expense balances and certain calculations used in preparing "
                "the statements for the current reporting period.")
    source = root / "sources/filing.html"
    source.write_text(source.read_text() + "<p>" + repeated + "</p>", encoding="utf-8")
    filing["content_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    save(index, {"filings": [filing]})
    prior = root / "previous"
    prior.mkdir()
    old = [{"article": {"summary": repeated}}]
    save(prior / "packet.json", old)
    save(prior / "freeze.json", {"packet_sha256": digest(old)})
    out = root / "result"
    receipt = prepare(index, metadata, root, out, [prior / "packet.json"])
    packet = json.loads((out / "packet.json").read_text())
    assert receipt["excluded_previously_labelled_passages"] == 1
    assert receipt["clusters"] == 1 and receipt["requested_clusters"] == 24
    assert not packet[0]["document_previously_exposed"]
    assert "factor_bindings" not in packet[0] and "prediction" not in packet[0]
    labels = out / "labels.json"
    save(labels, {"packet_sha256": digest(packet), "reference_kind": "AI_DEVELOPMENT_REVIEW",
                  "labels": [{"id": r["id"], "relevance": "NOT_RELEVANT",
                              "rationale": "Synthetic test only"} for r in packet]})
    assert evaluate(out, labels)["pairs"] == len(packet)
    (out / "source-audit.json").write_text("[]")
    with pytest.raises(ValueError, match="Source audit changed"):
        evaluate(out, labels)
