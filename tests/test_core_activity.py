import json

from engine.core_activity import assess
from engine.core_decisions import POLICY


def activity(text, entity=None):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    return assess(
        {"headline": "Infrastructure update", "excerpt": text},
        [
            {
                "entity_context": entity,
                "matches": [{"field": "summary", "start": 0, "end": len(text.rstrip("."))}],
            }
        ],
        policy,
    )


def test_generic_theme_is_not_company_change():
    assert (
        activity("The data center has maintained power availability.")["tier"] == "BACKGROUND_THEME"
    )
    assert (
        activity("Data center power shortages delayed deliveries.")["tier"]
        == "SECTOR_CHANGE_CONTEXT"
    )
    assert (
        activity("Data center power shortages did not delay deliveries.")["tier"]
        == "BACKGROUND_THEME"
    )
    r = activity("Data center power shortages could delay deliveries.")
    assert r["signals"][0]["phase"] == "FORWARD_LOOKING"
    assert r["direction"] == "UNKNOWN"


def test_resolved_relation_changes_priority_not_financial_claim():
    broad = activity("Data center demand increased.")
    direct = activity("Data center demand increased.", {"id": "verified-relation"})
    assert direct["editorial_score"] > broad["editorial_score"]
    assert direct["horizon"] == "UNKNOWN"


def test_source_duration_is_not_invented_company_impact_lag():
    result = activity("Data center power shortages delayed deliveries for 6 months.")
    assert result["signals"][0]["event_horizon"] == "MEDIUM"
    assert result["horizon"] == "UNKNOWN"
