"""One-step LLM knowledge overlay; never reported facts or premises for another inference."""

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.impact_atlas import read_snapshot
from engine.ingestion.contracts import digest

DEFAULT = Path(__file__).resolve().parent.parent / "config/knowledge-priors.json"


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    relation_types: list[Literal["USES_INPUT", "DEPENDS_ON", "COMPETES_WITH"]] = Field(min_length=1)
    target_kinds: list[str] = Field(min_length=1)
    dimension: str = Field(min_length=1)
    knowledge_basis: str = Field(min_length=30)
    common_knowledge: Literal[True]
    clarity: Literal["CLEAR"]
    applicability: str = Field(min_length=20)
    conditions: list[str] = Field(min_length=1)
    exceptions: list[str] = Field(min_length=1)
    unit: Literal["category", "fraction", "days"]
    category: str | None = None
    lower: Decimal | None = None
    upper: Decimal | None = None
    denominator: str | None = None
    estimation_method: str | None = None

    @model_validator(mode="after")
    def value_contract(self):
        if self.unit == "category":
            if not self.category or any(
                v is not None
                for v in [self.lower, self.upper, self.denominator, self.estimation_method]
            ):
                raise ValueError("Qualitative prior cannot invent numeric precision")
        elif (
            self.category is not None
            or self.lower is None
            or self.upper is None
            or not self.lower.is_finite()
            or not self.upper.is_finite()
            or not 0 <= self.lower < self.upper
            or (self.unit == "fraction" and self.upper > 1)
            or not self.denominator
            or not self.estimation_method
            or len(self.estimation_method) < 30
        ):
            raise ValueError(
                "Numeric prior needs finite nondegenerate interval, denominator and explicit estimation method"
            )
        return self


def load_rules(path=DEFAULT):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema") != "ONE_STEP_LLM_PRIORS_V1" or raw.get("delivery") != "disabled":
        raise ValueError("Unsupported knowledge policy")
    rules = [Rule.model_validate(r) for r in raw["rules"]]
    if not rules or len(rules) > 100 or len({r.id for r in rules}) != len(rules):
        raise ValueError("Bounded unique rule catalog required")
    return rules


def build(data, rules, *, author, at=None):
    """Only source-backed atlas relations are premises. Priors cannot be chained."""
    at = at or datetime.now(UTC)
    if (
        not author.strip()
        or at.tzinfo is None
        or at > datetime.now(UTC)
        or datetime.fromisoformat(data["as_of"]) > at
    ):
        raise ValueError("Known atlas, author and aware nonfuture time required")
    if data.get("delivery") != "disabled" or data.get("schema") != "IMPACT_ATLAS_V1":
        raise ValueError("Local atlas required; prior databases are not inference inputs")
    rules = [Rule.model_validate(r) for r in rules]
    if len({r.id for r in rules}) != len(rules) or len(rules) > 100:
        raise ValueError("Duplicate/oversized rules")
    nodes = {n["id"]: n for n in data["nodes"]}
    sources = {s["id"] for s in data["sources"]}
    exposures = {e["relation_id"]: e for e in data["exposures"]}
    rows, occupied = [], set()
    for edge in data["relations"]:
        if (
            edge["status"] != "SOURCE_BACKED"
            or edge["basis"] != "SOURCE_REPORTED"
            or not edge["eligible_at_snapshot"]
            or not edge["evidence"]
            or any(e["source_id"] not in sources or not e["quote"] for e in edge["evidence"])
            or datetime.fromisoformat(edge["known_at"]) > at
            or datetime.fromisoformat(edge["valid_from"]) > at
            or (edge["valid_until"] and at >= datetime.fromisoformat(edge["valid_until"]))
        ):
            continue
        for rule in rules:
            if (
                edge["type"] not in rule.relation_types
                or nodes[edge["to_id"]]["kind"] not in rule.target_kinds
            ):
                continue
            key = (edge["id"], rule.dimension)
            existing = exposures[edge["id"]]["dimensions"].get(
                rule.dimension, {"status": "UNKNOWN"}
            )
            if existing["status"] != "UNKNOWN":
                continue  # Never overwrite sourced, disputed or explicitly not-applicable data.
            if key in occupied:
                raise ValueError("Conflicting prior rules for the same relationship dimension")
            occupied.add(key)
            rows.append(
                {
                    "id": digest([edge["id"], rule.id, rule.version]),
                    "relation_id": edge["id"],
                    "profile_id": edge["profile_id"],
                    "from_id": edge["from_id"],
                    "to_id": edge["to_id"],
                    "scope": edge["scope"],
                    "dimension": rule.dimension,
                    "status": "LLM_PRIOR_UNVERIFIED",
                    "inference_steps": 1,
                    "premise_kind": "SOURCE_REPORTED_RELATION",
                    "premise_sha256": digest(edge),
                    "premise_evidence": edge["evidence"],
                    "knowledge_basis": rule.knowledge_basis,
                    "applicability": rule.applicability,
                    "conditions": rule.conditions,
                    "exceptions": rule.exceptions,
                    "unit": rule.unit,
                    "category": rule.category,
                    "lower": str(rule.lower) if rule.lower is not None else None,
                    "upper": str(rule.upper) if rule.upper is not None else None,
                    "denominator": rule.denominator,
                    "estimation_method": rule.estimation_method,
                    "rule_id": rule.id,
                    "rule_version": rule.version,
                    "rule_sha256": digest(rule.model_dump(mode="json")),
                    "author": author,
                    "author_kind": "LLM_OPERATOR",
                    "known_at": at.isoformat(),
                    "review_until": (at + timedelta(days=90)).isoformat(),
                    "use": "CONDITIONAL_RELEVANCE_OR_EXPLICIT_SCENARIO_ONLY",
                    "can_be_inference_premise": False,
                    "verified_impact": False,
                }
            )
    return {
        "schema": "ONE_STEP_LLM_PRIOR_DATABASE_V1",
        "atlas_sha256": digest(data),
        "created_at": at.isoformat(),
        "author": author,
        "rules": [r.model_dump(mode="json") for r in rules],
        "priors": rows,
        "delivery": "disabled",
        "active_feed_changed": False,
    }


def lookup(bundle, data, relation_id, dimension, *, at=None):
    """Sourced values win. An expired/replaced snapshot cannot supply fallback priors."""
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC) or datetime.fromisoformat(data["as_of"]) > at:
        raise ValueError("Invalid lookup time")
    for exposure in data["exposures"]:
        if exposure["relation_id"] == relation_id:
            value = exposure["dimensions"].get(dimension)
            if value and value["status"] != "UNKNOWN":
                return {"origin": "ATLAS", "value": value}
    if bundle["atlas_sha256"] != digest(data):
        return {"origin": "UNKNOWN", "reason": "ATLAS_CHANGED_REBUILD_PRIORS"}
    if (
        bundle.get("schema") != "ONE_STEP_LLM_PRIOR_DATABASE_V1"
        or bundle.get("delivery") != "disabled"
    ):
        raise ValueError("Invalid prior bundle")
    # Replay the one inference from source facts; output edits cannot create a second step.
    rebuilt = build(
        data,
        bundle["rules"],
        author=bundle["author"],
        at=datetime.fromisoformat(bundle["created_at"]),
    )
    if digest(rebuilt) != digest(bundle):
        raise ValueError("Prior bundle differs from its declared one-step derivation")
    edge = next((r for r in data["relations"] if r["id"] == relation_id), None)
    for prior in bundle["priors"]:
        if prior["relation_id"] == relation_id and prior["dimension"] == dimension:
            if (
                edge
                and prior["premise_sha256"] == digest(edge)
                and datetime.fromisoformat(prior["known_at"])
                <= at
                < datetime.fromisoformat(prior["review_until"])
                and (not edge["valid_until"] or at < datetime.fromisoformat(edge["valid_until"]))
            ):
                return {"origin": "LLM_PRIOR_UNVERIFIED", "value": prior}
    return {"origin": "UNKNOWN", "reason": "NO_CURRENT_APPLICABLE_PRIOR"}


def install(bundle, output):
    """New immutable research version, stored separately from source-reported facts."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(output / "priors.db") as conn:
        conn.executescript(
            "CREATE TABLE metadata (payload TEXT NOT NULL); CREATE TABLE priors (id TEXT PRIMARY KEY, relation_id TEXT NOT NULL, dimension TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(relation_id, dimension));"
        )
        conn.execute(
            "INSERT INTO metadata VALUES (?)",
            (json.dumps({k: v for k, v in bundle.items() if k != "priors"}),),
        )
        conn.executemany(
            "INSERT INTO priors VALUES (?,?,?,?)",
            [(p["id"], p["relation_id"], p["dimension"], json.dumps(p)) for p in bundle["priors"]],
        )
    (output / "priors.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "manifest.json").write_text(
        json.dumps(
            {
                name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                for name in ["priors.db", "priors.json"]
            }
        ),
        encoding="utf-8",
    )
    return {
        "priors": len(bundle["priors"]),
        "delivery": "disabled",
        "atlas_sha256": bundle["atlas_sha256"],
    }


def read(output):
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != {"priors.db", "priors.json"} or any(
        hashlib.sha256((output / name).read_bytes()).hexdigest() != expected
        for name, expected in manifest.items()
    ):
        raise ValueError("Prior database artifact changed")
    bundle = json.loads((output / "priors.json").read_text(encoding="utf-8"))
    if (
        bundle.get("schema") != "ONE_STEP_LLM_PRIOR_DATABASE_V1"
        or bundle.get("delivery") != "disabled"
    ):
        raise ValueError("Invalid prior database")
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--rules", type=Path, default=DEFAULT)
    parser.add_argument("--author", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            install(
                build(read_snapshot(args.atlas), load_rules(args.rules), author=args.author),
                args.output,
            )
        )
    )


if __name__ == "__main__":
    main()
