"""Synthetic scoped activity routing, not financial-impact validation."""

from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier

from engine.company_profiles import FactorBinding
from engine.profile_news import matches


def rule(**changes):
    now = datetime.now(UTC)
    return FactorBinding.model_validate(
        dict(
            id="named-compute",
            factor_id="compute",
            kind="SCOPED_ACTIVITY",
            topic_terms=["ExampleChip"],
            context_terms=["GPU", "GPUs", "AI", "compute", "cloud"],
            change_terms=["financing", "commits", "deploys", "expands", "access", "cancelled"],
            narrative_ids=["customer-buildout"],
            exclude_terms=["stock price", "price target"],
            scope="Synthetic customer infrastructure activity, not verified exposure.",
            reviewed_at=now,
            review_until=now + timedelta(days=1),
            evidence=[{"source_id": "test", "quote": "Synthetic infrastructure evidence."}],
            **changes,
        )
    )


@pytest.mark.parametrize(
    "title",
    [
        "Bank financing enables ExampleChip GPU purchases",
        "ExampleChip commits capital to AI buildout",
        "Cloud operator deploys ExampleChip GPUs",
        "Provider expands ExampleChip compute access",
        "ExampleChip GPU financing cancelled",
    ],
)
def test_scoped_activity_positive_and_negative_developments(title):
    hits = matches(rule(), {"title": title})
    assert len(hits) == 3
    assert all(title[h["start"] : h["end"]] == h["text"] for h in hits)
    assert all(h["scope_basis"] == "SAME_SENTENCE_TOPIC_ACTIVITY_NOT_VERIFIED_PARTY" for h in hits)


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "ExampleChip shares rise. Unrelated operator expands AI cloud"},
        {"title": "ExampleChip GPUs", "summary": "Unrelated operator expands cloud"},
        {"title": "ExampleChip stock price expands on AI excitement"},
        {"title": "ExampleChip CPUs are discussed; OtherVendor expands GPU cloud"},
        {"title": "ExampleChipper expands AI cloud"},
        {"title": "ExampleChip GPUs available"},
    ],
)
def test_unrelated_sentences_fields_and_missing_activity_held(payload):
    assert matches(rule(), payload) == []


def test_summary_offsets_preserve_prefix():
    text = "Other news. Cloud operator deploys ExampleChip GPUs."
    hits = matches(rule(), {"summary": text})
    assert len(hits) == 3 and all(h["field"] == "summary" for h in hits)
    assert all(text[h["start"] : h["end"]] == h["text"] for h in hits)


def test_explicit_narrative_scope_required():
    data = rule().model_dump()
    data["narrative_ids"] = []
    with pytest.raises(ValueError, match="explicit narratives"):
        FactorBinding.model_validate(data)


def test_enabled_orphan_binding_rejected_before_profile_activation(dossier):
    from engine.company_profiles import ProfileBundle, audit_binding_routes, stage

    root, data = dossier
    data["nodes"].append({"id": "orphan", "kind": "factor", "label": "Unconnected factor"})
    item = rule().model_dump(mode="json")
    item.update(
        factor_id="orphan",
        narrative_ids=[data["narratives"][0]["id"]],
        reviewed_at=data["available_at"],
        evidence=data["relationships"][0]["evidence"],
    )
    data["factor_bindings"] = [item]
    bundle = ProfileBundle.model_validate(data)
    with pytest.raises(ValueError, match="no sourced route"):
        audit_binding_routes(bundle)
    pointer = (root / "current.json").read_bytes()
    data["version"] = 2
    data["available_at"] = datetime.now(UTC).isoformat()
    with pytest.raises(ValueError, match="no sourced route"):
        stage(root, ProfileBundle.model_validate(data))
    assert (root / "current.json").read_bytes() == pointer
    assert not (root / "profile-v2.json").exists()
    item["enabled"] = False
    audit_binding_routes(ProfileBundle.model_validate(data))
