import hashlib
import json
from datetime import UTC, datetime

import pytest
from test_sec_event_groups import packet as packet

from engine.evaluation.scoped_operating_passages import approved_rows, freeze
from engine.ingestion.contracts import digest


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def scoped(packet, tmp_path):
    source, _ = packet
    family = json.loads((source / "packet.json").read_text())[0]
    doc = family["documents"][0]
    quote = (source / doc["text"]).read_text()
    scope = tmp_path / "scope"
    scope.mkdir()
    rows = [{"id": family["id"], "family": family, "document": doc,
             "quote": quote, "text_start": 0, "text_end": len(quote), "paragraph_index": 0}]
    save(scope / "packet.json", rows)
    save(scope / "receipt.json", {"packet_sha256": digest(rows)})
    paths = []
    for actor in "ab":
        path = tmp_path / ("scope-" + actor + ".json")
        save(path, {"reviewer_id": actor, "reviewer_kind": "AI_INDEPENDENT",
            "reviewed_at": datetime.now(UTC).isoformat(), "peer_reviews_accessed": False,
            "packet_sha256": digest(rows), "passages": [{"id": family["id"],
            "approved": True, "external_context_required": False,
            "scope": "EXACT_PASSAGE_INFORMATIONAL_ONLY", "economic_period": "2026-04-26",
            "quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
            "limitations": ["No whole-filing verification"]}]})
        paths.append(path)
    return scope, source, paths


def test_scope_preserves_limitations_and_original_span(scoped):
    scope, source, reviews = scoped
    rows, held = approved_rows(scope, source, reviews)
    assert len(rows) == 1 and not held
    assert rows[0]["limitations"] == ["No whole-filing verification"]
    assert rows[0]["period_citation"]["quote"] == "April 26, 2026"


@pytest.mark.parametrize("field,value", [("approved", False), ("external_context_required", True),
    ("scope", "WHOLE_FILING"), ("economic_period", "2026-04-27")])
def test_disagreement_cannot_release_passage(scoped, field, value):
    scope, source, reviews = scoped
    r = json.loads(reviews[0].read_text())
    r["passages"][0][field] = value
    save(reviews[0], r)
    rows, held = approved_rows(scope, source, reviews)
    assert not rows and len(held) == 1


def test_review_hash_and_bytes_not_optional(scoped):
    scope, source, reviews = scoped
    r = json.loads(reviews[0].read_text())
    r["passages"][0]["quote_sha256"] = "bad"
    save(reviews[0], r)
    with pytest.raises(ValueError, match="quote hash"):
        approved_rows(scope, source, reviews)


def test_scope_does_not_bypass_previous_period(scoped, tmp_path):
    scope, source, reviews = scoped
    old = tmp_path / "old"
    old.mkdir()
    rows = [{"archive_source": {"ticker": "TEST", "report_period": "2026-04-26"},
             "article": {"summary": "Different excerpt"}}]
    save(old / "packet.json", rows)
    save(old / "freeze.json", {"packet_sha256": digest(rows)})
    out = tmp_path / "out"
    r = freeze(scope, source, reviews, out, [old / "packet.json"])
    assert r["selected"] == 0 and r["previously_exposed"] == 1
    assert not (out / "predictions.json").exists()


def test_cited_future_period_is_not_a_realized_reporting_period(scoped):
    scope, source, reviews = scoped
    originals = json.loads((source / "packet.json").read_text())
    originals[0]["filing_date"] = "2026-04-25"
    save(source / "packet.json", originals)
    save(source / "receipt.json", {"packet_sha256": digest(originals)})
    rows = json.loads((scope / "packet.json").read_text())
    rows[0]["family"] = originals[0]
    save(scope / "packet.json", rows)
    save(scope / "receipt.json", {"packet_sha256": digest(rows)})
    for path in reviews:
        review = json.loads(path.read_text())
        review["packet_sha256"] = digest(rows)
        save(path, review)
    selected, held = approved_rows(scope, source, reviews)
    assert not selected and len(held) == 1


def test_sampling_protocol_is_recorded_without_relabeling(scoped, tmp_path, monkeypatch):
    import engine.evaluation.scoped_operating_passages as module

    scope, source, reviews = scoped
    protocol = "FIRST_UNQUOTED_REALIZED_PRODUCT_OR_SEGMENT_PARAGRAPH_V1"
    monkeypatch.setattr(module, "freeze_selected", lambda *args, **kwargs: kwargs["extra_receipt"])
    receipt = freeze(scope, source, reviews, tmp_path / "new", sampling_protocol=protocol)
    assert receipt["sampling"] == protocol
    assert receipt["scope_report"]["selected"] == 1


def test_unknown_sampling_protocol_cannot_freeze(scoped, tmp_path):
    scope, source, reviews = scoped
    with pytest.raises(ValueError, match="sampling protocol"):
        freeze(scope, source, reviews, tmp_path / "new", sampling_protocol="PICK_POSITIVES")
    assert not (tmp_path / "new").exists()
