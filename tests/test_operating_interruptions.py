import json

import pytest
from test_core_activity import activity

from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.operating_interruptions import assess as interruption


@pytest.mark.parametrize("name", ["Orion", "Cobalt"])
@pytest.mark.parametrize("template,selected", [
    ("Construction paused at {name} data center.", True),
    ("{name} halted construction of a data center.", True),
    ("{name} production was suspended.", True),
    ("{name} stopped shipments of components.", True),
    ("{name} plans to halt production.", True),
    ("{name} production will be halted.", True),
    ("{name} delayed a conference about production.", False),
    ("{name} halted share trading for a plant.", False),
    ("{name} might halt production.", False),
    ("{name} plans to avoid halted production.", False),
    ("{name} did not halt production.", False),
    ("{name} designed systems to stop production.", False),
    ("{name} suspended demonstrations while construction continues.", False),
    ("{name} factory staff halted marketing.", False),
    ("{name} factory could be halted.", False),
    ("{name} risks halted production.", False),
    ("{name} halted a meeting, construction continues.", False),
    ("Could {name} halt production?", False),
])
def test_interruption_uses_operating_object_and_asserted_phase(name, template, selected):
    text = template.format(name=name)
    result = activity(text)
    assert bool(result["signals"]) is selected
    assert result["direction"] == result["horizon"] == "UNKNOWN"
    if selected:
        signal = result["signals"][0]
        assert signal["event_type"] == "OPERATING_INTERRUPTION"
        d = signal["operating_development"]
        assert d["financial_impact"] == "UNKNOWN" and d["identity_verified"] is False
        for key in ["action_span", "object_span"]:
            s = d[key]
            assert text[s["start"]:s["end"]] == s["text"]
        if "plans to" in text or "will be" in text:
            assert signal["phase"] == "FORWARD_LOOKING"


def test_priority_cannot_create_relevance_or_borrow_a_headline():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    item = {"headline": "Construction paused at Orion data center.", "excerpt": "Orion overview."}
    assert not assess(item, [], policy)["signals"]
    unrelated = [{"matches": [{"field": "summary", "start": 0, "end": 5}]}]
    assert not assess(item, unrelated, policy)["signals"]
    assert interruption("Paused construction") is None


def test_source_duration_is_not_company_impact_horizon():
    result = activity("Construction paused for 12 days at Orion data center.")
    assert result["signals"][0]["source_duration"] == "for 12 days"
    assert result["horizon"] == "UNKNOWN"
