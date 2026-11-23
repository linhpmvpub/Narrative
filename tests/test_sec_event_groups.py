import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal as seal_profile

from engine.evaluation.sec_event_groups import evaluate, event_key, load_reviewed, prepare
from engine.ingestion.contracts import digest
from engine.sec_review import plain_text


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def packet(tmp_path):
    root = tmp_path / "sources"
    root.mkdir()
    raw = ("<p>Results for the quarter ended April 26, 2026. Our suppliers deliver components "
           "for servers and we discuss changes in capacity and customer demand under existing "
           "purchase agreements and uncertainties in the supply of memory products.</p>")
    text = plain_text(raw)
    (root / "source.html").write_bytes(raw.encode())
    (root / "source.txt").write_bytes(text.encode())
    family = {"id": "0000000001-26-000001", "ticker": "TEST", "cik": "0000000001",
        "filing_date": "2026-05-20", "report_period": "2026-05-20", "documents": [{
        "role": "primary", "url": "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/s.htm",
        "html": "source.html", "text": "source.txt", "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest()}]}
    save(root / "packet.json", [family])
    save(root / "receipt.json", {"packet_sha256": digest([family])})
    paths = []
    for actor in "ab":
        path = tmp_path / (actor + ".json")
        save(path, {"reviewer_id": actor, "reviewer_kind": "AI_INDEPENDENT",
            "reviewed_at": datetime.now(UTC).isoformat(), "peer_reviews_accessed": False,
            "packet_sha256": digest([family]), "families": [{"id": family["id"],
            "scoped_context_sufficient": True, "missing_or_external_context": [],
            "economic_period_or_event_date": "FY2027 Q1 ended 2026-04-26"}]})
        paths.append(path)
    return root, paths


def test_earnings_period_not_filing_date(packet):
    root, paths = packet
    family, votes, docs = load_reviewed(root, paths)[0]
    group = event_key(family, votes, docs)
    assert group["key"] == "0000000001:EARNINGS:2026-04-26"
    cite = group["citation"]
    assert docs[0][1][cite["start"]:cite["end"]] == cite["quote"]


def test_disagreement_or_uncited_date_withheld(packet):
    root, paths = packet
    family, votes, docs = load_reviewed(root, paths)[0]
    votes[1]["economic_period_or_event_date"] = "ended 2026-04-27"
    assert event_key(family, votes, docs) is None
    votes[0]["economic_period_or_event_date"] = "ended 2026-04-27"
    assert event_key(family, votes, docs) is None


def test_earnings_without_clear_reviewed_period_cannot_fall_back(packet):
    root, paths = packet
    family, votes, docs = load_reviewed(root, paths)[0]
    for v in votes:
        v["economic_period_or_event_date"] = "2026-04-26"
        v["event_kind"] = "earnings release"
    family["report_period"] = "2026-04-26"
    assert event_key(family, votes, docs) is None
    votes[0]["economic_period_or_event_date"] = "ended 2026-04-27"
    assert event_key(family, votes, docs) is None


def test_non_earnings_events_not_merged_by_date(packet):
    root, paths = packet
    family, votes, docs = load_reviewed(root, paths)[0]
    for v in votes:
        v["economic_period_or_event_date"] = "2026-04-26"
    family["report_period"] = "2026-04-26"
    a = event_key(family, votes, docs)
    family["id"] = "different-accession"
    b = event_key(family, votes, docs)
    assert a["key"] != b["key"] and a["kind"] == "ACCESSION_EVENT"


def test_prior_period_excludes_new_accession_and_different_excerpt(packet, tmp_path):
    root, paths = packet
    old = tmp_path / "old"
    old.mkdir()
    rows = [{"archive_source": {"ticker": "TEST", "report_period": "2026-04-26",
                                "accession": "different"}, "article": {"summary": "Different text"}}]
    save(old / "packet.json", rows)
    save(old / "freeze.json", {"packet_sha256": digest(rows)})
    result = prepare(root, paths, tmp_path / "out", [old / "packet.json"])
    assert result["disposition"] == {"PREVIOUS_ECONOMIC_PERIOD": 1}
    assert not (tmp_path / "out/predictions.json").exists()


def test_context_limitations_never_negative_samples(packet, tmp_path):
    root, paths = packet
    review = json.loads(paths[0].read_text())
    review["families"][0]["missing_or_external_context"] = ["Missing prior contract"]
    save(paths[0], review)
    result = prepare(root, paths, tmp_path / "out")
    assert result["disposition"] == {"EXTERNAL_CONTEXT_HELD": 1}


@pytest.mark.parametrize("fault", ["raw", "text", "peer", "identity", "packet", "coverage"])
def test_tamper_and_invalid_review_rejected(packet, fault):
    root, paths = packet
    if fault in {"raw", "text"}:
        (root / ("source.html" if fault == "raw" else "source.txt")).write_text("changed")
    elif fault == "packet":
        (root / "packet.json").write_text("[]")
    else:
        r = json.loads(paths[1].read_text())
        if fault == "peer":
            r["peer_reviews_accessed"] = True
        elif fault == "identity":
            r["reviewer_id"] = "a"
        else:
            r["families"] = []
        save(paths[1], r)
    with pytest.raises(ValueError):
        load_reviewed(root, paths)


def test_real_freeze_seals_grouping_and_hides_predictions(packet, dossier, tmp_path, monkeypatch):
    root, paths = packet
    profile_root, data = dossier
    data["factor_bindings"] = [{"id": "test", "factor_id": "f",
        "topic_terms": ["suppliers"], "context_terms": ["capacity"], "change_terms": ["demand"],
        "scope": "Synthetic", "reviewed_at": data["available_at"],
        "review_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "evidence": data["relationships"][0]["evidence"]}]
    seal_profile(profile_root, data)
    registry = tmp_path / "profiles"
    registry.mkdir()
    profile_root.rename(registry / "example")
    monkeypatch.setenv("COMPANY_PROFILE_ROOT", str(registry))
    out = tmp_path / "frozen"
    receipt = prepare(root, paths, out)
    rows = json.loads((out / "packet.json").read_text())
    assert receipt["clusters"] == 1 and receipt["packet_sha256"] == digest(rows)
    assert rows[0]["document_previously_exposed"] is True
    assert rows[0]["archive_source"]["event_group_key"].endswith("EARNINGS:2026-04-26")
    assert "factor_bindings" not in rows[0] and "prediction" not in rows[0]
    labels = out / "labels.json"
    save(labels, {"packet_sha256": digest(rows), "reference_kind": "AI_DEVELOPMENT_REVIEW",
        "labels": [{"id": r["id"], "relevance": "NOT_RELEVANT", "rationale": "Synthetic"}
                   for r in rows]})
    assert evaluate(out, labels)["pairs"] == len(rows)
    with pytest.raises(ValueError, match="Frozen output exists"):
        prepare(root, paths, out)
    (out / "grouping.json").write_text("[]")
    with pytest.raises(ValueError, match="Event grouping changed"):
        evaluate(out, labels)
