"""Scope failures must not remove valid same-window product/market evidence."""

from datetime import UTC, datetime

import pytest
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import get
from test_profile_news import linked as linked

from engine.article_cards import decisions as article_decisions
from engine.company_profiles import FactorBinding, ProfileBundle, withdraw
from engine.profile_news import matches
from engine.routing_guards import assess


@pytest.mark.parametrize("guard,title,text,allowed", [
    ("INFRASTRUCTURE_FINANCING", "Investment", "A venture fund is investing in AI infrastructure startups.", False),
    ("INFRASTRUCTURE_FINANCING", "Data center financing", "A fund is investing in startups.", False),
    ("INFRASTRUCTURE_FINANCING", "Construction", "The operator secured funding for a 500 MW data center.", True),
    ("INFRASTRUCTURE_FINANCING", "Construction", "The operator denied funding for a data center.", False),
    ("SERVER_COMPONENT_MARKET", "Automotive agreement", "Memory supply agreements cover automotive products.", False),
    ("SERVER_COMPONENT_MARKET", "Automotive memory", "The manufacturer agreed to supply memory.", False),
    ("SERVER_COMPONENT_MARKET", "Automotive and server update", "Enterprise SSDs face a supply shortage.", True),
    ("SERVER_COMPONENT_MARKET", "Input costs", "DRAM prices increased.", True),
    ("SECTOR_CONSTRAINT", "Procurement", "Two companies signed a memory supply agreement for data centers.", False),
    ("SECTOR_CONSTRAINT", "Shortage", "The operators face memory shortages in data centers.", True),
    ("SECTOR_CONSTRAINT", "Shortage", "Operators face no memory shortages in data centers.", False),
    ("SECTOR_CONSTRAINT", "Outlook", "Operators could face memory shortages in data centers.", False),
    ("SECTOR_CONSTRAINT", "Construction costs", "Data center developers face higher construction costs.", True),
])
def test_guard_boundaries(guard, title, text, allowed):
    trace = assess([guard], title, text)
    assert trace["allowed"] == allowed
    assert trace["financial_impact"] == "UNKNOWN"
    for check in trace["checks"]:
        if e := check["evidence"]:
            assert text[e["start"]:e["end"]] == e["text"]


def guarded(data, guard="SECTOR_CONSTRAINT"):
    d = dict(data["factor_bindings"][0])
    d.update(kind="SCOPED_ACTIVITY", narrative_ids=["n"], routing_guards=[guard])
    return FactorBinding.model_validate(d)


def test_guard_requires_explicit_target_and_preserves_legacy_hash(linked):
    _, data, _, _, _ = linked
    d = guarded(data).model_dump(mode="json")
    d["narrative_ids"] = []
    with pytest.raises(ValueError, match="explicit activity narratives"):
        FactorBinding.model_validate(d)
    d["narrative_ids"] = ["n"]
    d["routing_guards"] *= 2
    with pytest.raises(ValueError, match="unique constraints"):
        FactorBinding.model_validate(d)
    assert "routing_guards" not in FactorBinding.model_validate(data["factor_bindings"][0]).model_dump(mode="json")


def test_guard_and_match_must_share_window_with_exact_offsets(linked):
    _, data, _, _, _ = linked
    b = guarded(data)
    assert not matches(b, {"title": "Memory shortages", "summary": "Server memory supply agreement."})
    assert not matches(b, {"summary": "Server memory supply agreement. Food shortages continued."})
    text = "An unrelated introduction. Server memory supply shortages increased."
    hits = matches(b, {"summary": text})
    assert hits
    for h in hits:
        assert text[h["start"]:h["end"]] == h["text"]
        trace = h["routing_guard_trace"]
        e = trace["checks"][0]["evidence"]
        assert trace["window_text"][e["start"]:e["end"]] == e["text"]


def test_full_article_keeps_guard_window_offsets(linked):
    _, data, _, _, _ = linked
    data["factor_bindings"] = [guarded(data).model_dump(mode="json")]
    b = ProfileBundle.model_validate(data)
    text = "Overview only. Server memory supply shortages increased."
    rows = list(article_decisions(b, b.narratives[0], "Market update",
                                 [{"text": text, "source_spans": []}], datetime.now(UTC)))
    assert rows
    for h in rows[0]["matches"]:
        assert text[h["start"]:h["end"]] == h["text"]
        assert h["routing_guard_trace"]["allowed"]


def test_guard_survives_source_to_card_and_withdrawal(db, linked):
    root, data, insert, _, _ = linked
    data["factor_bindings"] = [guarded(data).model_dump(mode="json")]
    seal(root, data)
    insert(title="Server memory supply agreement", summary="Bilateral agreement announced.")
    assert not get(db)["items"]
    insert(title="Server memory supply shortages increased", summary="Industry update.")
    card = get(db)["items"][0]
    assert card["links"][0]["matches"][0]["routing_guard_trace"]["allowed"]
    assert card["delivery"] == "disabled" and card["impact"] == "UNKNOWN"
    withdraw(root)
    assert not get(db)["items"]
