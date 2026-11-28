"""Narrative-independent company assessment over source-bound discovery evidence."""

import json
import re
from pathlib import Path

from engine.core_activity import assess as source_activity
from engine.core_decisions import POLICY as SOURCE_POLICY
from engine.editorial_priority import exclusion
from engine.ingestion.contracts import digest

POLICY = Path(__file__).resolve().parents[1] / "config/company-assessment-v1.json"


def assess(item, discoveries):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if policy["schema"] != "COMPANY_ASSESSMENT_V1" or policy["delivery"] != "disabled":
        raise ValueError("Disabled company assessment policy required")
    source_policy = json.loads(SOURCE_POLICY.read_text(encoding="utf-8"))
    signals, decisions, channels = [], [], []
    issuer_development = False
    for discovery in discoveries:
        unit = discovery.get("source_unit") or {"title": item["headline"], "summary": item["excerpt"]}
        context = {"headline": unit.get("title", ""), "excerpt": unit.get("summary", "")}
        spans = discovery["matches"]
        if discovery["kind"] == "ISSUER_EVENT":
            for span in spans:
                text = unit.get(span["field"], "")
                valid = text[span["start"]:span["end"]] == span["text"]
                event = span.get("issuer_event")
                window = event["source_window"] if event else None
                if window:
                    valid = (valid and window["field"] == span["field"]
                             and 0 <= window["start"] <= span["start"] < span["end"] <= window["end"] <= len(text)
                             and text[window["start"]:window["end"]] == window["text"])
                reason = exclusion(window["text"] if window else text) if valid else "SOURCE_SPAN_MISMATCH"
                eligible = valid and reason is None
                decisions.append({"eligible": eligible, "reason": reason or "EXPLICIT_ISSUER_EVENT",
                                  "rule_id": discovery["rule_id"]})
                if eligible:
                    issuer_development = True
                    signals.append({**span, "phase": event["phase"] if event else "SOURCE_REPORTED", "driver_direction": "UNKNOWN",
                                    "rule_id": discovery["rule_id"]})
        else:
            matches = [{**s, "routing_contract": discovery["routing_contract"]} for s in spans]
            activity = source_activity(context, [{"matches": matches,
                                        "entity_context": discovery.get("entity_context")}], source_policy)
            signals.extend({**s, "rule_id": discovery["rule_id"]} for s in activity["signals"])
            # The shared source-scoping helper predates company scope. Retain its
            # original reason as provenance, but do not claim a narrative was checked.
            decisions.extend({**d, "scope": "COMPANY", "rule_id": discovery["rule_id"]}
                             for d in activity["editorial_decisions"])
        for edge in discovery["path"]:
            channel = {"relation_id": edge["id"], "type": edge["type"], "scope": edge["scope"],
                       "conditions": edge["conditions"], "evidence": edge["evidence"],
                       "direction": "UNKNOWN", "magnitude": "UNKNOWN", "horizon": "UNKNOWN"}
            if channel not in channels:
                channels.append(channel)
    sponsored = bool(re.search(r"\b(sponsored|advertorial|partner content)\b", item["headline"], re.I))
    tier = ("SPONSORED_CONTEXT" if sponsored else "ISSUER_DEVELOPMENT" if issuer_development
            else "EXPOSURE_DEVELOPMENT" if signals else "RELATED_BACKGROUND")
    # No discoveries means not relevant; callers cannot promote unrelated text.
    attention = bool(discoveries) and tier in policy["attention_tiers"]
    return {"schema": policy["schema"], "relevant": bool(discoveries), "priority": attention,
            "tier": tier, "rank": policy["tiers"][tier], "rank_basis": policy["rank_basis"],
            "policy_sha256": digest(policy), "signals": signals, "decisions": decisions,
            "business_channels": channels, "sponsored": sponsored,
            "evidence_status": "SOURCE_REPORTED_WITH_REVIEWED_COMPANY_SCOPE",
            "direction": "UNKNOWN", "financial_magnitude": "UNKNOWN", "horizon": "UNKNOWN",
            "unknowns": policy["unknowns"], "delivery": "disabled",
            "narratives_used": False,
            "explanation": "Nguồn nêu diễn biến cụ thể trong phạm vi công ty; tác động tài chính chưa xác định."
            if attention else "Có căn cứ liên quan đến công ty; chưa đủ bằng chứng để ưu tiên như diễn biến mới."}


def project(card):
    assessment = assess(card, card["company_discovery"])
    return {**card, "assessment": assessment, "priority": assessment["tier"],
            "revision_sha256": digest([card["revision_sha256"], assessment]),
            "mode": "COMPANY_INTELLIGENCE_V1", "narratives": [],
            "decision_trace": [*card["decision_trace"], "Company assessment independent of narrative inventory"]}
