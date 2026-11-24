"""Read-only readiness audit for reusable, identity-anchored news scope rules."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from engine.company_profiles import available_bundles, paths
from engine.ingestion.contracts import digest
from engine.structured_news import GroundingRule, validate_rule


def audit(rules, *, profile_root=None, at=None):
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Nonfuture aware audit time required")
    if len(rules) > 500 or len({r.id for r in rules}) != len(rules):
        raise ValueError("Bounded unique rules required")
    registry = available_bundles(at, root=profile_root)
    if not registry["enabled"] or registry.get("withheld") or registry.get("truncated"):
        raise ValueError("Complete validated profile registry required")
    bundles = {b.id: b for b in registry["items"]}
    fingerprint = digest([b.model_dump(mode="json") for b in registry["items"]])
    results = []
    for rule in rules:
        targets = []
        try:
            if rule.profile_id not in bundles:
                raise ValueError("UNKNOWN_PROFILE")
            if rule.identity_reference_id is None:
                raise ValueError("MISSING_IDENTITY_ANCHOR")
            b = bundles[rule.profile_id]
            e = validate_rule(rule, b, at)
            if rule.status != "SOURCE_BACKED" or e.status != "SOURCE_BACKED":
                raise ValueError("INACTIVE_RULE_OR_EDGE")
            for n in b.narratives:
                routes, truncated = paths(
                    b, SimpleNamespace(anchors=[e.from_id]), n, effective_at=at
                )
                if not truncated and any(e.id in {x.id for x in p} for p in routes):
                    targets.append(n.id)
            if not targets:
                raise ValueError("NO_CURRENT_DIRECTED_SCOPE_PATH")
            reason = "READY_FOR_SHADOW_ONLY"
        except ValueError as error:
            reason = str(error)
        results.append(
            {
                "rule_id": rule.id,
                "profile_id": rule.profile_id,
                "status": reason,
                "narratives": targets,
            }
        )
    coverage = []
    for b in bundles.values():
        selected = [r for r in results if r["profile_id"] == b.id]
        coverage.append(
            {
                "profile_id": b.id,
                "ticker": b.ticker,
                "ready_rules": sum(r["status"] == "READY_FOR_SHADOW_ONLY" for r in selected),
                "held_rules": sum(r["status"] != "READY_FOR_SHADOW_ONLY" for r in selected),
                "exact_entity_references": sum(
                    r.resolution == "EXACT_ENTITY" for r in b.entity_references
                ),
                "narratives_covered": sorted(
                    {
                        n
                        for r in selected
                        if r["status"] == "READY_FOR_SHADOW_ONLY"
                        for n in r["narratives"]
                    }
                ),
                "limitation": "Rule readiness is not event recall, exposure magnitude or company completeness",
            }
        )
    current = available_bundles(at, root=profile_root)
    if (
        not current["enabled"]
        or current.get("withheld")
        or current.get("truncated")
        or digest([b.model_dump(mode="json") for b in current["items"]]) != fingerprint
    ):
        raise ValueError("Registry changed during scope audit")
    return {
        "at": at.isoformat(),
        "rules_sha256": digest([r.model_dump(mode="json") for r in rules]),
        "profiles_sha256": fingerprint,
        "rules": results,
        "coverage": coverage,
        "delivery": "disabled",
        "semantic_review": "AI_OPERATOR_OR_HUMAN_DECLARATION_NOT_GOLD",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        [
            GroundingRule.model_validate(x)
            for x in json.loads(args.rules.read_text(encoding="utf-8"))
        ],
        profile_root=args.profiles,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                "rules": len(result["rules"]),
                "ready": sum(r["status"] == "READY_FOR_SHADOW_ONLY" for r in result["rules"]),
                "delivery": "disabled",
            }
        )
    )


if __name__ == "__main__":
    main()
