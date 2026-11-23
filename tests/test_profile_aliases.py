"""Reviewed phrase variants preserve original spans; no global fuzzy expansion."""

from datetime import UTC, datetime, timedelta

import pytest

from engine.company_profiles import FactorBinding
from engine.profile_news import matches


def rule(**changes):
    now = datetime.now(UTC)
    data = {"id": "power", "factor_id": "power", "topic_terms": ["data center"],
            "context_terms": ["power"], "change_terms": ["shortage"],
            "exclude_terms": ["video game"],
            "term_aliases": {"data center": ["data centre", "data-center"],
                             "shortage": ["shortages"], "video game": ["videogame"]},
            "scope": "Synthetic scoped infrastructure rule", "reviewed_at": now,
            "review_until": now + timedelta(days=10),
            "evidence": [{"source_id": "synthetic", "quote": "Synthetic infrastructure evidence"}]}
    return FactorBinding.model_validate({**data, **changes})


@pytest.mark.parametrize("title", ["Data centre power shortages", "Data-center power shortage",
                                   "Data center power shortage"])
def test_variants_keep_exact_original_spans(title):
    spans = matches(rule(), {"title": title, "summary": ""})
    assert len(spans) == 3
    for span in spans:
        assert title[span["start"]:span["end"]] == span["text"]
        assert span["alias_used"] == (span["matched_term"] != span["term"])
    assert spans[0]["term"] == "data center"


@pytest.mark.parametrize("title", ["Data centrepiece power shortages", "Data centre shortages",
                                   "Data centre power overview", "Videogame data centre power shortages",
                                   "Hotel power shortages", "Data centres power shortages"])
def test_aliases_do_not_remove_context_or_expand_unreviewed_words(title):
    assert matches(rule(), {"title": title, "summary": ""}) == []


@pytest.mark.parametrize("aliases", [{"unknown": ["data centre"]},
                                     {"data center": ["DATA CENTER"]},
                                     {"data center": []},
                                     {"data center": ["data centre", "DATA CENTRE"]},
                                     {"data center": [" x "]},
                                     {"data center": ["variant" + str(i) for i in range(9)]}])
def test_alias_contract_rejects_ambiguous_or_unbounded_rules(aliases):
    with pytest.raises(ValueError):
        rule(term_aliases=aliases)


def test_aliases_are_literal_and_legacy_defaults_are_unchanged():
    binding = rule(term_aliases={"data center": ["data.*center"]})
    assert not matches(binding, {"title": "data hello center power shortage", "summary": ""})
    assert matches(binding, {"title": "data.*center power shortage", "summary": ""})
    assert not matches(rule(term_aliases={}), {"title": "Data centre power shortage", "summary": ""})
