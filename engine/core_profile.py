"""Seven-group v1 projection over existing sourced profiles, without duplicate facts."""

import json
from pathlib import Path

from engine.ingestion.contracts import digest

DEFAULT = Path(__file__).resolve().parent.parent / "config/core-profile-v1.json"


def project(data, registry, policy_path=DEFAULT):
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    if (
        policy["schema"] != "CORE_PROFILE_V1"
        or policy["delivery"] != "disabled"
        or registry.atlas_sha256 != digest(data)
    ):
        raise ValueError("Core profile policy or atlas mismatch")
    profiles = []
    for p in data["profiles"]:
        components = {c["key"]: c for c in data["components"] if c["profile_id"] == p["id"]}
        profiles.append(
            {
                "profile_id": p["id"],
                "ticker": p["ticker"],
                "legal_name": p["legal_name"],
                "groups": {
                    name: {
                        "components": [
                            {
                                "key": key,
                                "status": components[key]["status"]
                                if key in components
                                else "UNKNOWN",
                                "reference": components[key]["id"] if key in components else None,
                            }
                            for key in keys
                        ]
                    }
                    for name, keys in policy["groups"].items()
                },
                "product_node_ids": [
                    n["id"]
                    for n in data["nodes"]
                    if n["profile_id"] == p["id"] and n["kind"] in {"product", "segment"}
                ],
                "input_exposure_ids": [e.id for e in registry.exposures if e.profile_id == p["id"]],
                "narrative_ids": [
                    n["id"] for n in data["narratives"] if n["profile_id"] == p["id"]
                ],
                "core_relation_ids": [
                    r["id"]
                    for r in data["relations"]
                    if r["profile_id"] == p["id"] and r["type"] in policy["core_relations"]
                ],
            }
        )
    return {
        "schema": "CORE_PROFILE_V1",
        "policy_sha256": digest(policy),
        "atlas_sha256": digest(data),
        "input_registry_sha256": digest(registry.model_dump(mode="json")),
        "profiles": profiles,
        "source_of_truth": "REFERENCED_ATLAS_AND_INPUT_REGISTRY",
        "delivery": "disabled",
    }
