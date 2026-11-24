"""Immutable local exposure database and mechanism atlas, separate from live alerts."""
import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from engine.ingestion.contracts import digest

MECHANISMS: dict[str, dict[str, Any]] = {
    "supply_disruption": {"title": "Gián đoạn nguồn cung", "driver": "Mức gián đoạn", "channel": "input_availability", "sign": -1,
        "conditions": ["Đúng đầu vào và phạm vi cơ sở", "Tồn kho/nguồn thay thế không bù hết"],
        "mitigants": ["inventory_days", "substitutability", "supplier_concentration"]},
    "input_price": {"title": "Thay đổi giá đầu vào", "driver": "Giá đầu vào", "channel": "unit_cost", "sign": 1,
        "conditions": ["Giá mới áp dụng với hợp đồng mua", "Phân biệt chi phí và biên lợi nhuận"],
        "mitigants": ["contract_reset_days", "pass_through", "hedging"]},
    "capacity": {"title": "Mở rộng/thu hẹp công suất", "driver": "Công suất", "channel": "production_capacity", "sign": 1,
        "conditions": ["Có vốn, thiết bị và giấy phép", "Phân biệt kế hoạch, lắp đặt và vận hành"],
        "mitigants": ["ramp_days", "utilization", "yield"]},
    "demand": {"title": "Thay đổi nhu cầu", "driver": "Nhu cầu", "channel": "order_opportunity", "sign": 1,
        "conditions": ["Đúng thị trường/sản phẩm", "Nhu cầu chưa đồng nghĩa đơn hàng của công ty"],
        "mitigants": ["market_share", "customer_concentration", "competition"]},
    "technology": {"title": "Thay đổi công nghệ", "driver": "Năng lực kỹ thuật", "channel": "technical_capability", "sign": 1,
        "conditions": ["Kiểm tra chỉ tiêu kỹ thuật và điều kiện đo", "Mẫu thử chưa đồng nghĩa sản xuất hàng loạt"],
        "mitigants": ["qualification_days", "substitutability", "yield"]},
    "financing": {"title": "Tài trợ/cam kết vốn", "driver": "Nguồn vốn khả dụng", "channel": "funded_capacity_option", "sign": 1,
        "conditions": ["Đúng đơn vị nhận vốn và mục đích sử dụng", "Cam kết chưa đồng nghĩa giải ngân hoặc công suất"],
        "mitigants": ["funding_conditions", "ramp_days", "permit_status"]},
    "policy": {"title": "Chính sách/cấp phép", "driver": "Mức hạn chế", "channel": "market_access", "sign": -1,
        "conditions": ["Đúng khu vực, sản phẩm và pháp nhân", "Kiểm tra hiệu lực, ngoại lệ và thời hạn"],
        "mitigants": ["exemptions", "geographic_mix", "substitutability"]},
}
DIMENSIONS = ["exposure_share", "supplier_concentration", "supplier_concentration_qualitative", "customer_concentration", "substitutability",
              "inventory_days", "contract_reset_days", "pass_through", "hedging", "ramp_days",
              "utilization", "yield", "market_share", "competition", "qualification_days",
              "funding_conditions", "permit_status", "exemptions", "geographic_mix", "duration_days"]
GROUPS = {
    "products_revenue": ["products", "segments", "revenue_model", "sales_mix"],
    "supply_capacity": ["inputs", "suppliers", "facilities", "capacity"],
    "customers_demand": ["customers", "channels", "markets", "demand_drivers"],
    "prices_contracts": ["selling_prices", "input_prices", "inventory", "procurement"],
    "funding_financials": ["financials", "debt", "capital_events", "strategy"],
    "technology_competition": ["technology", "competition", "partners"],
    "geography_hazards": ["regulation", "geopolitics", "weather", "utilities", "logistics"],
}


def key(profile, local):
    return profile + "/" + local


def snapshot(profile_root, at=None, facts=()):
    from engine.company_profiles import COMPONENTS, RELATIONS, available_bundles
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Aware nonfuture snapshot required")
    registry = available_bundles(at, root=profile_root)
    if not registry["enabled"] or registry.get("withheld") or registry.get("truncated") or not registry["items"]:
        raise ValueError("Complete integrity-checked profile registry required")
    result: dict = {"schema": "IMPACT_ATLAS_V1", "as_of": at.isoformat(), "delivery": "disabled",
        "scope": "LOCAL_RESEARCH_SNAPSHOT_NOT_LIVE_VERIFICATION", "profiles": [], "nodes": [],
        "relations": [], "sources": [], "narratives": [], "components": [], "exposures": [],
        "mechanisms": MECHANISMS, "groups": GROUPS, "dimensions": DIMENSIONS,
        "policy": {"version": "uncalibrated-v1", "weights": None, "financial_magnitude": "UNKNOWN",
                   "calibration_status": "PENDING_GROUPED_INDEPENDENT_EVALUATION"}}
    for b in registry["items"]:
        pid = b.id
        result["profiles"].append({"id": pid, "ticker": b.ticker, "version": b.version,
            "legal_name": b.legal_name, "available_at": b.available_at.isoformat(),
            "sha256": digest(b.model_dump(mode="json"))})
        for n in b.nodes:
            result["nodes"].append({**n.model_dump(), "id": key(pid, n.id), "profile_id": pid})
        for s in b.sources:
            result["sources"].append({**s.model_dump(mode="json", exclude={"file"}),
                                      "id": key(pid, s.id), "profile_id": pid})
        def evidence(items, pid=pid):
            return [{"source_id": key(pid, e.source_id), "quote": e.quote} for e in items]
        for r in b.relationships:
            active = (r.status == "SOURCE_BACKED" and r.known_at <= at and r.valid_from <= at
                      and (r.valid_until is None or at < r.valid_until))
            row = {**r.model_dump(mode="json"), "id": key(pid, r.id), "profile_id": pid,
                "from_id": key(pid, r.from_id), "to_id": key(pid, r.to_id),
                "family": RELATIONS[r.type][0], "eligible_at_snapshot": active,
                "evidence": evidence(r.evidence)}
            result["relations"].append(row)
            # This is a scoped relationship inventory, not proof of quantified dependence.
            result["exposures"].append({"id": row["id"], "profile_id": pid,
                "relation_id": row["id"], "scope": r.scope, "basis": r.basis,
                "dimensions": {d: {"status": "UNKNOWN", "value": None, "unit": None,
                    "evidence": []} for d in DIMENSIONS},
                "legacy_lag_text": r.lag, "legacy_direction": r.direction,
                "status": "UNQUANTIFIED_RELATIONSHIP_CONTEXT"})
        components = {c.key: c for c in b.components}
        for name, title in COMPONENTS.items():
            c = components.get(name)
            result["components"].append({"id": key(pid, name), "profile_id": pid, "key": name,
                "title": title, "status": c.status if c else "UNKNOWN",
                "summary": c.summary if c else "Chưa có dữ liệu đã rà soát",
                "evidence": evidence(c.evidence) if c else []})
        for n in b.narratives:
            if n.available_at <= at:
                result["narratives"].append({**n.model_dump(mode="json"), "id": key(pid, n.id),
                    "profile_id": pid, "company_id": key(pid, n.company_id),
                    "watched_nodes": [key(pid, x) for x in n.watched_nodes]})
    check = available_bundles(at, root=profile_root)
    if (check.get("withheld") or check.get("truncated") or
            [digest(b.model_dump(mode="json")) for b in check["items"]] !=
            [p["sha256"] for p in result["profiles"]]):
        raise ValueError("Registry changed during snapshot")
    apply_facts(result, facts, profile_root, registry["items"], at)
    result["coverage"] = coverage(result)
    return result


def coverage(data):
    rows = []
    for p in data["profiles"]:
        components = {c["key"]: c for c in data["components"] if c["profile_id"] == p["id"]}
        relations = [r for r in data["relations"] if r["profile_id"] == p["id"]]
        rows.append({"profile_id": p["id"], "ticker": p["ticker"],
            "groups": {g: {"sourced": [k for k in keys if components[k]["status"] == "SOURCED"],
                           "gaps": [k for k in keys if components[k]["status"] != "SOURCED"]}
                       for g, keys in GROUPS.items()},
            "relations": len(relations), "eligible_relations": sum(r["eligible_at_snapshot"] for r in relations),
            "quantified_exposures": sum(any(d["status"] == "SOURCED" and d["unit"] in {"fraction", "days"}
                for d in e["dimensions"].values()) for e in data["exposures"] if e["profile_id"] == p["id"]),
            "acceptance": "REVIEW_COVERAGE_AND_EXPOSURE_GAPS"})
    return rows


class FactEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    quote: str = Field(min_length=1, max_length=4000)


class ExposureFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    relation_id: str
    dimension: str
    value: str = Field(min_length=1, max_length=2000)
    unit: Literal["fraction", "days", "category"]
    scope: str = Field(min_length=1, max_length=2000)
    valid_from: AwareDatetime
    valid_until: AwareDatetime | None = None
    known_at: AwareDatetime
    reviewed_at: AwareDatetime
    reviewer_id: str = Field(min_length=1)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]
    evidence: list[FactEvidence] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def dimensions(self):
        if self.dimension not in DIMENSIONS:
            raise ValueError("Unknown exposure dimension")
        fractions = {"exposure_share", "supplier_concentration", "customer_concentration", "pass_through",
                     "utilization", "yield", "market_share", "geographic_mix"}
        expected = "fraction" if self.dimension in fractions else "days" if self.dimension.endswith("_days") else "category"
        if self.unit != expected:
            raise ValueError("Exposure dimension/unit mismatch")
        if expected != "category":
            try:
                number = Decimal(self.value)
            except InvalidOperation as exc:
                raise ValueError("Numeric exposure value required") from exc
            if not number.is_finite() or number < 0 or (expected == "fraction" and number > 1):
                raise ValueError("Invalid exposure value")
        if (self.known_at > self.reviewed_at or
                (self.valid_until is not None and self.valid_until <= self.valid_from)):
            raise ValueError("Invalid exposure chronology")
        return self


def apply_facts(data, facts, profile_root, bundles, at):
    """Explicit reviewed facts; no numerical parsing or automatic strength assignment."""
    from engine.company_profiles import source_text
    if len(facts) > 2000:
        raise ValueError("Bounded exposure facts required")
    exposures = {e["id"]: e for e in data["exposures"]}
    bundle_by_id = {b.id: b for b in bundles}
    # Resolve directories by validated profile identity, not by an assumed directory name.
    directories = {}
    for directory in Path(profile_root).iterdir():
        if directory.is_dir() and (directory / "current.json").exists():
            receipt = json.loads((directory / "current.json").read_text(encoding="utf-8"))
            directories[receipt["id"]] = directory
    used, ids = set(), set()
    data["exposure_facts"] = []
    for raw in facts:
        fact = ExposureFact.model_validate(raw)
        exposure = exposures.get(fact.relation_id)
        if exposure is None or fact.id in ids or fact.reviewed_at > at:
            raise ValueError("Unknown relation, duplicate fact or future review")
        ids.add(fact.id)
        bundle = bundle_by_id[exposure["profile_id"]]
        sources = {key(bundle.id, s.id): s for s in bundle.sources}
        for e in fact.evidence:
            source = sources.get(e.source_id)
            if source is None or source.retrieved_at > fact.known_at:
                raise ValueError("Fact source identity/time invalid")
            directory = directories[bundle.id].resolve()
            path = (directory / source.file).resolve()
            if not path.is_relative_to(directory):
                raise ValueError("Fact source outside profile")
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != source.sha256 or e.quote not in source_text(body):
                raise ValueError("Fact evidence changed or quote unsupported")
        value = fact.model_dump(mode="json")
        data["exposure_facts"].append(value)
        if fact.valid_from <= at and (fact.valid_until is None or at < fact.valid_until):
            identity = (fact.relation_id, fact.dimension)
            if identity in used:
                raise ValueError("Overlapping exposure facts require explicit resolution")
            used.add(identity)
            exposure["dimensions"][fact.dimension] = {"status": "SOURCED", **value}


SQL = """
PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE profiles(id TEXT PRIMARY KEY, ticker TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0), payload TEXT NOT NULL);
CREATE TABLE nodes(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id), kind TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE sources(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id), payload TEXT NOT NULL);
CREATE TABLE relations(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id),
 from_id TEXT NOT NULL REFERENCES nodes(id), to_id TEXT NOT NULL REFERENCES nodes(id),
 eligible INTEGER NOT NULL CHECK(eligible IN (0,1)), payload TEXT NOT NULL);
CREATE TABLE evidence(relation_id TEXT NOT NULL REFERENCES relations(id), source_id TEXT NOT NULL REFERENCES sources(id), quote TEXT NOT NULL);
CREATE TABLE exposures(id TEXT PRIMARY KEY REFERENCES relations(id), profile_id TEXT NOT NULL REFERENCES profiles(id), payload TEXT NOT NULL);
CREATE TABLE exposure_facts(id TEXT PRIMARY KEY, relation_id TEXT NOT NULL REFERENCES relations(id), version INTEGER NOT NULL CHECK(version>0), payload TEXT NOT NULL);
CREATE TABLE fact_evidence(fact_id TEXT NOT NULL REFERENCES exposure_facts(id), source_id TEXT NOT NULL REFERENCES sources(id), quote TEXT NOT NULL);
CREATE TABLE components(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id), payload TEXT NOT NULL);
CREATE TABLE narratives(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id), payload TEXT NOT NULL);
CREATE TABLE mechanisms(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
"""


def install(data, output):
    """One new directory per snapshot. Never overwrite an older database or map."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    db = sqlite3.connect(output / "atlas.db")
    def encode(value):
        return json.dumps(value, ensure_ascii=False)
    try:
        db.executescript(SQL)
        with db:
            db.execute("INSERT INTO metadata VALUES (?,?)", ("snapshot", encode(data)))
            for p in data["profiles"]:
                db.execute("INSERT INTO profiles VALUES (?,?,?,?)", (p["id"], p["ticker"], p["version"], encode(p)))
            for n in data["nodes"]:
                db.execute("INSERT INTO nodes VALUES (?,?,?,?)", (n["id"], n["profile_id"], n["kind"], encode(n)))
            for name in ["sources", "components", "narratives", "exposures"]:
                if name == "exposures":
                    continue  # Relations must exist first.
                db.executemany(f"INSERT INTO {name} VALUES (?,?,?)",
                    [(r["id"], r["profile_id"], encode(r)) for r in data[name]])
            for r in data["relations"]:
                db.execute("INSERT INTO relations VALUES (?,?,?,?,?,?)", (r["id"], r["profile_id"],
                    r["from_id"], r["to_id"], int(r["eligible_at_snapshot"]), encode(r)))
                db.executemany("INSERT INTO evidence VALUES (?,?,?)",
                    [(r["id"], e["source_id"], e["quote"]) for e in r["evidence"]])
            db.executemany("INSERT INTO exposures VALUES (?,?,?)",
                [(r["id"], r["profile_id"], encode(r)) for r in data["exposures"]])
            for fact in data["exposure_facts"]:
                db.execute("INSERT INTO exposure_facts VALUES (?,?,?,?)",
                           (fact["id"], fact["relation_id"], fact["version"], encode(fact)))
                db.executemany("INSERT INTO fact_evidence VALUES (?,?,?)",
                    [(fact["id"], e["source_id"], e["quote"]) for e in fact["evidence"]])
            db.executemany("INSERT INTO mechanisms VALUES (?,?)", [(k, encode(v)) for k, v in MECHANISMS.items()])
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Broken atlas references")
    finally:
        db.close()
    (output / "atlas.json").write_text(encode(data), encoding="utf-8")
    from engine.impact_atlas_web import render
    render(data, output / "index.html")
    manifest = {"schema": data["schema"], "as_of": data["as_of"], "delivery": "disabled",
        "files": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                  for name in ["atlas.db", "atlas.json", "index.html"]}}
    (output / "manifest.json").write_text(encode(manifest), encoding="utf-8")
    return {"profiles": len(data["profiles"]), "nodes": len(data["nodes"]),
            "relations": len(data["relations"]), "delivery": "disabled"}


def read_snapshot(root):
    root = Path(root)
    receipt = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name in ["atlas.db", "atlas.json", "index.html"]:
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != receipt["files"][name]:
            raise ValueError("Atlas artifact changed")
    data = json.loads((root / "atlas.json").read_text(encoding="utf-8"))
    if data["schema"] != "IMPACT_ATLAS_V1" or data["as_of"] != receipt["as_of"]:
        raise ValueError("Atlas schema/time mismatch")
    return data


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mechanism_id: str
    factor_id: str
    direction: Literal["UP", "DOWN"]
    phase: Literal["PROPOSED", "COMMITTED", "OPERATING"]
    lag_min_days: int | None = Field(default=None, ge=0)
    lag_max_days: int | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=0)
    scope: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def ordered(self):
        if ((self.lag_min_days is None) != (self.lag_max_days is None) or
            (self.lag_min_days is not None and self.lag_max_days is not None and self.lag_min_days > self.lag_max_days)):
            raise ValueError("Complete ordered lag interval required")
        if self.mechanism_id not in MECHANISMS:
            raise ValueError("Unknown mechanism")
        return self


def scenario(data, event):
    """Hypothetical topology only. Generic channels never assign signed graph edges."""
    nodes = {n["id"]: n for n in data["nodes"]}
    if event.factor_id not in nodes:
        raise ValueError("Factor must identify an atlas node")
    profile = nodes[event.factor_id]["profile_id"]
    edges = [r for r in data["relations"] if r["profile_id"] == profile and r["eligible_at_snapshot"]]
    paths: list[dict] = []
    truncated = False
    for n in data["narratives"]:
        if n["profile_id"] != profile:
            continue
        pending: list[tuple[str, list[str], set[str], int, int]] = [(event.factor_id, [], {event.factor_id}, 0, 0)]
        visits = 0
        while pending:
            if visits >= 2000 or len(paths) >= 20:
                truncated = True
                break
            node, route, seen, structural, mechanisms = pending.pop(0)
            visits += 1
            if node in n["watched_nodes"]:
                paths.append({"narrative_id": n["id"], "relations": route,
                              "status": "TOPOLOGICAL_CANDIDATE_SCOPE_REVIEW_REQUIRED",
                              "financial_direction": "UNKNOWN", "strength": "UNKNOWN"})
                continue
            for r in edges:
                if r["from_id"] != node or r["to_id"] in seen:
                    continue
                m = mechanisms + int(r["family"] == "MECHANISM")
                s = structural + int(r["family"] == "STRUCTURAL")
                if m <= 2 and s <= 3:
                    pending.append((r["to_id"], route+[r["id"]], seen | {r["to_id"]}, s, m))
    mechanism = MECHANISMS[event.mechanism_id]
    signed = mechanism["sign"] * (1 if event.direction == "UP" else -1)
    return {"mode": "HYPOTHETICAL_OPERATOR_SCENARIO", "event": event.model_dump(),
        "mechanism": event.mechanism_id, "generic_channel": mechanism["channel"],
        "conditional_channel_direction": "UP" if signed > 0 else "DOWN",
        "conditions": mechanism["conditions"], "required_exposure_fields": mechanism["mitigants"],
        "realized_effect": "NOT_ESTABLISHED", "financial_magnitude": "UNKNOWN",
        "horizon": {"lag_min_days": event.lag_min_days, "lag_max_days": event.lag_max_days,
                    "duration_days": event.duration_days, "basis": "OPERATOR_ASSUMPTION_NOT_INFERRED"},
        "paths": paths, "truncated": truncated, "delivery": "disabled", "price_prediction": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "scenario", "verify"])
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--facts", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        if args.profiles is None:
            parser.error("--profiles required")
        facts = json.loads(args.facts.read_text(encoding="utf-8")) if args.facts else []
        result = install(snapshot(args.profiles, facts=facts), args.output)
    else:
        data = read_snapshot(args.output)
        if args.action == "scenario":
            if args.input is None:
                parser.error("--input scenario JSON required")
            result = scenario(data, Scenario.model_validate(json.loads(args.input.read_text(encoding="utf-8"))))
        else:
            result = {"verified": True, "as_of": data["as_of"], "delivery": "disabled"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
