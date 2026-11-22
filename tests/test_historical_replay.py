"""Archive-mode isolation, freeze integrity, grouping and blind-label boundaries."""

import copy
import hashlib
from datetime import UTC, datetime

import pytest

from engine.evaluation import historical_replay as h


def test_selection_groups_issuer_period_and_rejects_sndk_pre_spin():
    recent = {"form": ["10-Q", "10-Q", "10-Q/A"],
              "filingDate": ["2024-05-01", "2024-05-02", "2024-05-03"],
              "accessionNumber": ["0000000001-24-000001", "0000000001-24-000002",
                                  "0000000001-24-000003"],
              "primaryDocument": ["a.htm"] * 3, "reportDate": ["2024-03-31"] * 3}
    rows = h.selection("MU", "1", recent)
    assert len(rows) == 1
    assert rows[0]["known_amendments"] == ["0000000001-24-000003"]
    assert h.selection("SNDK", "1", recent) == []
    recent["primaryDocument"][0] = "../../secret.html"
    with pytest.raises(ValueError):
        h.selection("MU", "1", recent)


def text(n):
    return "<html>" + "".join("<p>" + s + "</p>" for s in [
        f"Revenue increased in reporting period {n} because customers purchased more equipment. "
        "The company described the change in its quarterly results and associated operating costs.",
        f"For reporting period {n}, higher costs may reduce operating income in future periods. "
        "Management cannot determine the magnitude of the potential effects or when they may occur.",
        f"For reporting period {n}, revenue recognition follows the described accounting policy. "
        "The company records sales when the performance obligation has been satisfied for customers.",
    ]) + "</html>"


@pytest.fixture
def frozen(tmp_path):
    sources = []
    for n in range(50):
        path = tmp_path / f"{n}.html"
        path.write_bytes(text(n).encode())
        sources.append({"cluster_key": f"MU:{n}", "file": path.name,
                        "url": f"https://example.test/synthetic/{n}",
                        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "filing_date": "2025-01-01", "ticker": "MU"})
    h.write(tmp_path / "collection.json", {"sources": sources, "errors": []})
    h.freeze(tmp_path)
    return tmp_path


def review(pack, profile="retail_investor"):
    return {"track": h.TRACK, "profile": profile, "packet_id": pack["packet_id"],
            "blind_to_predictions": True, "blind_to_other_reviews": True,
            "reviewed_at": datetime.now(UTC).isoformat(),
            "labels": [{"case_id": c["id"], "source_sha256": c["source_sha256"],
                        "passages": [{"language": "NO_CAUSAL_CLAIM", "impact_sign": "UNKNOWN",
                                      "numeric_effect_supported": False,
                                      "quote": p["text"][:30],
                                      "reason": "Synthetic independent test reference."}
                                     for p in c["passages"]]} for c in pack["cases"]]}


def test_freeze_blinds_and_keeps_production_replay_separate(frozen):
    pack, sealed, receipt = h.verify(frozen)
    assert receipt["clusters"] == 50 and receipt["passages"] == 150
    assert "predictions" not in pack
    assert sealed["delivery"] == "disabled"
    assert sealed["graph_policy"] == "UNAVAILABLE_NO_POINT_IN_TIME_VERIFIED_GRAPH"
    assert h.partition("2023-12-31") == "development"
    assert h.partition("2024-12-31") == "calibration"
    with pytest.raises(FileExistsError):
        h.freeze(frozen)


@pytest.mark.parametrize("name", ["0.html", "blind-input.json", "sealed-predictions.json",
                                  "collection.json"])
def test_tampering_rejected(frozen, name):
    with (frozen / name).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError):
        h.verify(frozen)


@pytest.mark.parametrize("fault", ["quote", "duplicate", "early", "unblind", "numeric"])
def test_review_integrity(frozen, fault):
    pack, _, receipt = h.verify(frozen)
    r = review(pack)
    h.validate_review(pack, r, receipt["frozen_at"])
    if fault == "quote":
        r["labels"][0]["passages"][0]["quote"] = "invented quote absent from evidence"
    elif fault == "duplicate":
        r["labels"][-1] = copy.deepcopy(r["labels"][0])
    elif fault == "early":
        r["reviewed_at"] = "2020-01-01T00:00:00+00:00"
    elif fault == "unblind":
        r["blind_to_predictions"] = False
    else:
        r["labels"][0]["passages"][0]["numeric_effect_supported"] = "false"
    with pytest.raises(ValueError):
        h.validate_review(pack, r, receipt["frozen_at"])


def test_three_votes_report_unknown_product_metrics(frozen):
    pack, _, _ = h.verify(frozen)
    for profile in h.PROFILES:
        h.write(frozen / (profile + ".json"), review(pack, profile))
    report = h.evaluate(frozen)
    assert report["counts"]["unanimous"] == 150
    assert report["push_precision"] is None
    assert report["two_hop_recall"] is None
    assert report["human_labels"] == report["graph_promotions"] == 0


def test_source_parser_excludes_hidden_text():
    passages = h.excerpts("<script>Invented revenue increased</script>" + text(1))
    assert len(passages) == 3
    assert not any("Invented" in p["text"] for p in passages)


@pytest.mark.parametrize("fault", [None, "stale", "quote", "missing", "dossier"])
def test_disagreement_adjudication_is_source_bound(frozen, fault):
    pack, _, _ = h.verify(frozen)
    for profile in h.PROFILES:
        r = review(pack, profile)
        if profile == "fund_manager":
            r["labels"][0]["passages"][0]["language"] = "ISSUER_ATTRIBUTION"
        h.write(frozen / (profile + ".json"), r)
    assert h.disagreements(frozen)["disagreements"] == 1
    dossier = h.read(frozen / "disagreements.json")
    row = dossier["disagreements"][0]
    decision = {"case_id": row["case_id"], "passage": row["passage"],
                "vote_sha256": row["vote_sha256"], "outcome": "RESOLVED",
                "label": row["votes"]["fund_manager"]}
    adjudication = {"track": h.TRACK, "profile": "financial_expert",
                   "packet_id": pack["packet_id"], "blind_to_predictions": True,
                   "independent_review_sha256": dossier["independent_review_sha256"],
                   "reviewed_at": datetime.now(UTC).isoformat(), "decisions": [decision]}
    if fault == "stale":
        decision["vote_sha256"] = "0" * 64
    elif fault == "quote":
        decision["label"]["quote"] = "invented absent quote"
    elif fault == "missing":
        adjudication["decisions"] = []
    elif fault == "dossier":
        dossier["disagreements"][0]["text"] = "Replaced evidence"
        (frozen / "disagreements.json").unlink()
        h.write(frozen / "disagreements.json", dossier)
    h.write(frozen / "adjudication.json", adjudication)
    if fault:
        with pytest.raises(ValueError):
            h.evaluate(frozen)
    else:
        result = h.evaluate(frozen)
        assert result["status"] == "BLIND_REVIEW_COMPLETE"
        assert result["adjudicated_passages"] == 1
