from copy import deepcopy

import pytest

from engine.evaluation import benchmark as b
from engine.evaluation.company_quality import (
    SCORE_POLICY,
    company_report,
    company_rows,
    headline,
    identity,
)
from engine.evaluation.priority_review import company_consensus


def row(target="supply", label="RELEVANT", selected=False, **extra):
    return dict(id=target, ticker="RENAMED", groups=["capacity"], event_cluster="economic-event",
                source_unit_id="article-version-1", target_id=target,
                label=label, priority="PRIORITY" if label == "RELEVANT" else "NONE",
                selected=selected, main=selected, **extra)


def test_company_discovery_does_not_erase_narrative_error():
    rows = [row(), row("demand", selected=True)]
    assert b.dimension(rows, "relevance")["overall"]["fn"] == 1
    assert company_report(rows)["overall"]["tp"] == 1
    rows[1]["label"] = "NOT_RELEVANT"
    assert b.dimension(rows, "relevance")["overall"]["fp"] == 1
    assert company_report(rows)["overall"]["tp"] == 1
    assert b.dimension(rows, "relevance")["by_narrative"]["supply"]["fn"] == 1


def test_complete_negative_proxy_and_incomplete_or_unknown_units():
    rows = [row(label="NOT_RELEVANT"), row("demand", label="NOT_RELEVANT"),
            {**row(label="NOT_RELEVANT"), "source_unit_id": "second"}]
    units = company_rows(rows)
    assert [u["label"] for u in units] == ["NOT_RELEVANT", "INSUFFICIENT_CONTEXT"]
    rows[1]["label"] = "INSUFFICIENT_CONTEXT"
    assert company_report(rows)["overall"]["unresolved"] == 2


def test_direct_company_event_outside_watched_narratives_is_a_miss():
    rows = [row(label="NOT_RELEVANT", company_label="RELEVANT")]
    assert company_report(rows)["overall"]["fn"] == 1
    assert b.dimension(rows, "relevance")["overall"]["tn"] == 1


@pytest.mark.parametrize("fault", ["duplicate", "conflict", "missing", "contradiction"])
def test_company_references_fail_closed(fault):
    rows = [row(company_label="RELEVANT"), row("demand", company_label="RELEVANT")]
    if fault == "duplicate":
        rows[1]["target_id"] = rows[0]["target_id"]
    elif fault == "conflict":
        rows[1]["company_label"] = "NOT_RELEVANT"
    elif fault == "missing":
        del rows[1]["company_label"]
    else:
        for r in rows:
            r["company_label"] = "NOT_RELEVANT"
    with pytest.raises(ValueError):
        company_rows(rows)


def test_economic_cluster_does_not_merge_distinct_articles_or_revisions():
    value = {"article": {"url": "https://example.test/a", "title": "Source", "summary": "v1"},
             "profile_id": "company", "narrative": {"id": "supply"}}
    first = identity(value)
    value["article"]["summary"] = "v2"
    second = identity(value)
    assert first["source_unit_id"] != second["source_unit_id"]
    rows = [{**row(selected=True), **first}, {**row(), **second}]
    m = company_report(rows)["overall"]
    assert (m["tp"], m["fn"], m["clusters"]) == (1, 1, 1)


def scored(rows):
    return {"anchor": {"company": company_report(rows),
                       **{d: b.dimension(rows, d) for d in ("relevance", "priority")}}}


CONFIG = {"policy": SCORE_POLICY, "anchor": "anchor"}


def test_fixed_index_balances_misses_and_unknown_coverage_without_true_negatives():
    rows = [row(selected=True, company_label="RELEVANT")]
    assert headline(scored(rows), CONFIG)["score"] == 100
    unknown = {**row("uncertain", label="INSUFFICIENT_CONTEXT", company_label="INSUFFICIENT_CONTEXT"),
               "source_unit_id": "another", "priority": "INSUFFICIENT_CONTEXT"}
    result = headline(scored(rows + [unknown]), CONFIG)
    assert result["score"] == 50
    assert result["components"]["company"]["unresolved"] == 1
    rows[0]["selected"] = rows[0]["main"] = False
    assert headline(scored(rows), CONFIG)["score"] == 0


def test_absent_priority_or_direct_company_support_never_becomes_perfect_score():
    r = row(selected=True, company_label="RELEVANT")
    r["priority"] = None
    result = headline(scored([r]), CONFIG)
    assert result["score"] is None and result["missing_support"] == ["priority"]
    assert headline(scored([row(selected=True)]), CONFIG)["score"] is None
    assert headline({}, None)["status"] == "NOT_CONFIGURED"
    with pytest.raises(ValueError):
        headline(scored([r]), {"policy": {}, "anchor": "anchor"})


def test_partially_unlabelled_priority_penalizes_coverage():
    rows = [row(selected=True, company_label="RELEVANT"),
            {**row(selected=True, company_label="RELEVANT"), "source_unit_id": "second", "priority": None}]
    result = headline(scored(rows), CONFIG)
    assert result["score"] == 90
    assert result["components"]["priority"]["unlabelled_pairs"] == 1


def reviews():
    units = [{"id": "company1", "pair_ids": ["pair1"]}]
    a = {"labels": [{"id": "pair1", "relevance": "NOT_RELEVANT"}],
         "company_labels": [{"id": "company1", "relevance": "RELEVANT", "rationale": "Business event"}]}
    return units, [a, deepcopy(a)]


def test_company_disagreement_is_independent_of_narrative_agreement():
    units, votes = reviews()
    votes[1]["company_labels"][0]["relevance"] = "INSUFFICIENT_CONTEXT"
    result = company_consensus(votes, units)
    assert result["disagreements"] == 1
    assert result["labels"][0]["relevance"] == "INSUFFICIENT_CONTEXT"


@pytest.mark.parametrize("fault", ["missing", "duplicate", "invalid", "rationale", "contradiction"])
def test_company_review_requires_complete_consistent_votes(fault):
    units, votes = reviews()
    labels = votes[0]["company_labels"]
    if fault == "missing":
        labels.clear()
    elif fault == "duplicate":
        labels.append(deepcopy(labels[0]))
    elif fault == "invalid":
        labels[0]["relevance"] = "YES"
    elif fault == "rationale":
        labels[0]["rationale"] = ""
    else:
        votes[0]["labels"][0]["relevance"] = "RELEVANT"
        labels[0]["relevance"] = "NOT_RELEVANT"
    with pytest.raises(ValueError):
        company_consensus(votes, units)
