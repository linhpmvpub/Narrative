import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from engine.adapters.http_sources import AcquiredDocument
from engine.collect_sec import collect
from engine.evaluation.language_audit import protocol
from engine.evaluation.prospective import collect_new, prepare, read, verify

NOW = datetime.now(UTC)
TEXT = "Revenue increased this quarter because demand for our products improved significantly."
NEGATIVE = (
    "The company maintains offices in several locations and employs a broad range of professionals."
)


class Client:
    def fetch(self, url, **kwargs):
        tickers = ["MU", "NVDA", "AMD", "DELL", "SNDK"]
        if url.endswith("company_tickers.json"):
            text = json.dumps(
                {str(i): {"ticker": t, "cik_str": i + 1, "title": t} for i, t in enumerate(tickers)}
            )
        elif "submissions" in url:
            cik = int(url.split("CIK")[1].split(".")[0])
            text = json.dumps(
                {
                    "cik": cik,
                    "tickers": [tickers[cik - 1]],
                    "filings": {
                        "recent": {
                            "accessionNumber": [f"{cik:010d}-26-000001"],
                            "filingDate": [str(NOW.date())],
                            "form": ["10-Q"],
                            "primaryDocument": ["filing.htm"],
                        }
                    },
                }
            )
        else:
            text = f"<html><head><style>{TEXT}</style></head><body><p>{TEXT}</p><p>{NEGATIVE}</p></body></html>"
        return AcquiredDocument(
            url,
            text,
            NOW,
            hashlib.sha256(text.encode()).hexdigest(),
            hashlib.sha256(url.encode()).hexdigest(),
        )


@pytest.fixture
def setup(tmp_path):
    directory = tmp_path / "collection"
    collect(Client(), directory, NOW.date(), NOW.date())
    plan = protocol([], NOW - timedelta(days=2))
    return directory, plan, tmp_path / "run"


def test_freeze_deduplicates_and_blinds(setup):
    directory, plan, out = setup
    receipt = prepare(directory, plan, out, now=NOW)
    assert receipt["cases"] == 2
    assert len(receipt["rejections"]) == 8
    assert all(r["reasons"] == ["EXACT_TEXT_REUSE"] for r in receipt["rejections"])
    pack = read(out / "blind-input.json")
    assert "predictions" not in pack
    assert {c["text"] for c in pack["cases"]} == {TEXT, NEGATIVE}
    assert verify(out)["integrity"] == "verified"
    with pytest.raises(ValueError, match="already exists"):
        prepare(directory, plan, out, now=NOW)


def test_hash_tamper_prevents_freeze(setup):
    directory, plan, out = setup
    next(directory.glob("*.html")).write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare(directory, plan, out, now=NOW)
    assert not out.exists()


def test_identity_tamper_prevents_freeze(setup):
    directory, plan, out = setup
    data = read(directory / "collection.json")
    data["filings"][0]["url"] = "https://evil.example/filing.html"
    (directory / "collection.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="disagrees"):
        prepare(directory, plan, out, now=NOW)
    assert not out.exists()


def test_empty_date_window_has_no_network(tmp_path):
    class NoNetwork:
        def fetch(self, url, **kwargs):
            raise AssertionError("network called")

    plan = protocol([], NOW)
    assert collect_new(NoNetwork(), tmp_path / "unused", plan, NOW)["status"].startswith("WAITING")
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize("change", ["future", "exposed", "drift", "same_day"])
def test_invalid_inputs_never_freeze(setup, change):
    directory, plan, out = setup
    if change == "future":
        now = NOW - timedelta(days=1)
    else:
        now = NOW
    if change == "exposed":
        plan["seen_text"] = [
            __import__("engine.evaluation.language_audit", fromlist=["signature"]).signature(t)
            for t in [TEXT, NEGATIVE]
        ]
    if change == "drift":
        plan["candidate_sha256"] = "bad"
    if change == "same_day":
        plan["frozen_at"] = NOW.isoformat()
    with pytest.raises(ValueError):
        prepare(directory, plan, out, now=now)
    assert not out.exists()


@pytest.mark.parametrize(
    "filename", ["blind-input.json", "sealed-predictions.json", "protocol.json"]
)
def test_freeze_integrity_tamper(setup, filename):
    directory, plan, out = setup
    prepare(directory, plan, out, now=NOW)
    data = read(out / filename)
    if filename == "blind-input.json":
        data["predictions"] = {}
    elif filename == "sealed-predictions.json":
        data["predictions"] = {}
    else:
        data["frozen_at"] = NOW.isoformat()
    (out / filename).write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(out)


def test_review_handoff_round_trip(setup, tmp_path):
    from engine.evaluation.prospective import review_run

    directory, plan, out = setup
    prepare(directory, plan, out, now=NOW)
    pack = read(out / "blind-input.json")
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    for filename, profile in [
        ("reviewer-a.json", "retail_investor"),
        ("reviewer-b.json", "fund_manager"),
    ]:
        review = {
            "evaluation_track": "AI_SIMULATED",
            "packet_id": pack["packet_id"],
            "profile": profile,
            "blind_to_predictions": True,
            "labels": [
                {
                    "case_id": c["id"],
                    "source_sha256": c["source_sha256"],
                    "language": "NO_CAUSAL_CLAIM",
                    "numeric": None,
                    "reason": "Synthetic test vote, not a real evaluation",
                }
                for c in pack["cases"]
            ],
        }
        (reviews / filename).write_text(json.dumps(review))
    from engine.evaluation.review_release import release

    anchor = tmp_path / "anchor.json"
    released = release(out, tmp_path / "handoff", anchor)
    kwargs = {"anchor_path": anchor, "anchor_sha256": released["anchor_sha256"]}
    review_run(out, reviews, "disputes", **kwargs)
    assert read(reviews / "disputes.json")["disagreements"] == []
    (reviews / "expert.json").write_text(
        json.dumps(
            {
                "evaluation_track": "AI_SIMULATED",
                "packet_id": pack["packet_id"],
                "profile": "financial_expert",
                "blind_to_predictions": True,
                "decisions": [],
            }
        )
    )
    review_run(out, reviews, "evaluate", **kwargs)
    assert read(reviews / "summary.json")["total_cases"] == 2
    assert read(reviews / "summary.json")["human_labels_created"] == 0


@pytest.mark.parametrize(
    "change", ["predictions_and_receipt", "anchor", "reviewer_input", "extra_file"]
)
def test_release_rejects_tampering_even_with_locally_rehashed_receipt(setup, tmp_path, change):
    from engine.evaluation.review_release import release, verify_handoff
    from engine.ingestion.contracts import digest

    directory, plan, out = setup
    prepare(directory, plan, out, now=NOW)
    handoff, anchor = tmp_path / "handoff", tmp_path / "anchor.json"
    released = release(out, handoff, anchor)
    assert (
        verify_handoff(out, handoff, anchor, released["anchor_sha256"])["integrity"] == "verified"
    )
    if change == "predictions_and_receipt":
        sealed = read(out / "sealed-predictions.json")
        sealed["predictions"] = {cid: "tampered" for cid in sealed["predictions"]}
        (out / "sealed-predictions.json").write_text(json.dumps(sealed))
        receipt = read(out / "receipt.json")
        receipt["prediction_sha256"] = digest(
            {k: sealed[k] for k in ("predictions", "extractor", "as_of")}
        )
        (out / "receipt.json").write_text(json.dumps(receipt))
        assert verify(out)["integrity"] == "verified"  # Local receipt alone cannot detect this.
    elif change == "anchor":
        value = read(anchor)
        value["cases"] += 1
        anchor.write_text(json.dumps(value))
    elif change == "reviewer_input":
        (handoff / "retail_investor.json").write_text("{}")
    else:
        (handoff / "sealed-predictions.json").write_text("{}")
    with pytest.raises(ValueError):
        verify_handoff(out, handoff, anchor, released["anchor_sha256"])


def test_release_is_private_minimal_and_never_overwritten(setup, tmp_path):
    from engine.evaluation.review_release import release

    directory, plan, out = setup
    prepare(directory, plan, out, now=NOW)
    anchor, handoff = tmp_path / "anchor.json", tmp_path / "handoff"
    release(out, handoff, anchor)
    public = anchor.read_text()
    assert TEXT not in public and NEGATIVE not in public
    for path in handoff.iterdir():
        value = read(path)
        assert "predictions" not in value and "receipt" not in value
        assert set(value["cases"][0]) == {
            "id",
            "kind",
            "split",
            "ticker",
            "accession",
            "source_sha256",
            "url",
            "filing_date",
            "available_at",
            "text",
        }
    with pytest.raises(ValueError, match="already exists"):
        release(out, handoff, anchor)
    with pytest.raises(ValueError, match="outside"):
        release(out, tmp_path / "other", out / "bad-anchor.json")
