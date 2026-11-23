"""Versioned local company dossiers and evidence-bound narrative news routing.

This is informational relevance, not price forecasting or global graph approval.
Shared examples never contain user subscriptions or personal narrative notes.
"""

import hashlib
import json
import os
from collections import Counter, deque
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from engine.evaluation.prospective import Paragraphs
from engine.settings import Settings

ID = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")]
TEXT = Annotated[str, Field(min_length=1, max_length=4000)]
COMPONENTS = {
    "identity": "Danh tính pháp lý", "securities": "Chứng khoán và niêm yết",
    "ownership": "Cấu trúc tập đoàn", "segments": "Phân khúc kinh doanh",
    "products": "Sản phẩm và dịch vụ", "revenue_model": "Mô hình doanh thu",
    "strategy": "Chiến lược và phân bổ vốn", "selling_prices": "Giá bán",
    "sales_mix": "Sản lượng và cơ cấu bán", "customers": "Khách hàng",
    "end_users": "Người dùng cuối", "channels": "Kênh phân phối",
    "markets": "Thị trường địa lý", "demand_drivers": "Động lực nhu cầu",
    "orders": "Đơn hàng và cam kết", "competition": "Cạnh tranh và thay thế",
    "partners": "Đối tác và hệ sinh thái", "inputs": "Nguyên liệu và linh kiện",
    "suppliers": "Nhà cung cấp trực tiếp", "upstream": "Nhà cung cấp gián tiếp",
    "input_prices": "Giá đầu vào", "procurement": "Điều khoản mua hàng",
    "facilities": "Cơ sở hoạt động", "capacity": "Công suất và vận hành",
    "inventory": "Tồn kho", "logistics": "Logistics", "utilities": "Năng lượng và nước",
    "workforce": "Lao động", "resilience": "Khả năng chống chịu",
    "financials": "Đặc điểm tài chính", "debt": "Nợ và thanh khoản",
    "fx_hedging": "Ngoại tệ và phòng hộ", "accounting": "Phạm vi kế toán",
    "management": "Quản trị", "insider_trades": "Giao dịch người nội bộ",
    "related_party": "Giao dịch bên liên quan", "capital_events": "Sự kiện vốn",
    "regulation": "Pháp lý và chính sách", "geopolitics": "Địa chính trị",
    "weather": "Thời tiết và thiên tai", "technology": "Công nghệ và an ninh",
    "calendar": "Lịch sự kiện",
}
# A tuple declares family, allowed source kinds, allowed target kinds.
RELATIONS = {
    "OWNS": ("STRUCTURAL", {"company"}, {"company", "facility"}),
    "ISSUES": ("STRUCTURAL", {"company"}, {"security"}),
    "HAS_SEGMENT": ("STRUCTURAL", {"company"}, {"segment"}),
    "SELLS": ("STRUCTURAL", {"company", "segment"}, {"product"}),
    "USES_INPUT": ("STRUCTURAL", {"product", "segment", "facility"}, {"input"}),
    "SUPPLIES": ("STRUCTURAL", {"company", "supplier"}, {"product", "company", "segment"}),
    "BUYS": ("STRUCTURAL", {"company", "customer"}, {"product"}),
    "SOLD_IN": ("STRUCTURAL", {"product", "segment"}, {"market"}),
    "LOCATED_IN": ("STRUCTURAL", {"facility", "company"}, {"location"}),
    "DISTRIBUTES": ("STRUCTURAL", {"channel", "partner", "company"}, {"product"}),
    "PARTNERS_WITH": ("STRUCTURAL", {"company"}, {"partner", "company"}),
    "COMPETES_WITH": ("STRUCTURAL", {"company", "product"}, {"company", "product"}),
    "HAS_METRIC": ("STRUCTURAL", {"company", "segment", "product"}, {"metric"}),
    "APPLIES_TO": ("STRUCTURAL", {"factor", "contract"}, {"product", "market", "company", "facility"}),
    "DEPENDS_ON": ("STRUCTURAL", {"facility", "product", "segment"}, {"input", "supplier", "location", "factor"}),
    "AFFECTS_COST": ("MECHANISM", {"input", "factor", "contract"}, {"metric"}),
    "AFFECTS_SUPPLY": ("MECHANISM", {"factor", "facility", "supplier", "location", "input"}, {"product", "input"}),
    "AFFECTS_DEMAND": ("MECHANISM", {"factor", "market", "customer"}, {"product", "metric"}),
    "AFFECTS_ACCESS": ("MECHANISM", {"factor"}, {"market", "product"}),
    "AFFECTS_REVENUE": ("MECHANISM", {"market", "product", "factor"}, {"metric"}),
    "AFFECTS_MARGIN": ("MECHANISM", {"metric", "factor"}, {"metric"}),
    "AFFECTS_CASH": ("MECHANISM", {"metric", "factor", "contract"}, {"metric"}),
    "AFFECTS_FINANCING": ("MECHANISM", {"factor", "contract"}, {"metric"}),
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(Strict):
    id: ID
    url: HttpUrl
    file: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    published_at: AwareDatetime
    retrieved_at: AwareDatetime

    @model_validator(mode="after")
    def chronology(self):
        if self.url.scheme != "https" or self.published_at > self.retrieved_at:
            raise ValueError("HTTPS source and truthful acquisition clock required")
        return self


class Evidence(Strict):
    source_id: ID
    quote: TEXT


class Component(Strict):
    key: str
    status: Literal["SOURCED", "UNKNOWN", "NOT_DISCLOSED", "NOT_APPLICABLE", "STALE", "DISPUTED"]
    summary: TEXT
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def known_component(self):
        if self.key not in COMPONENTS or (self.status == "SOURCED" and not self.evidence):
            raise ValueError("Unknown component or missing source")
        return self


class Node(Strict):
    id: ID
    kind: Literal["company", "security", "segment", "product", "customer", "supplier",
                  "input", "facility", "market", "location", "factor", "metric", "partner",
                  "person", "channel", "contract"]
    label: TEXT


class Relationship(Strict):
    id: ID
    type: str
    from_id: ID
    to_id: ID
    scope: TEXT
    valid_from: AwareDatetime
    valid_until: AwareDatetime | None = None
    known_at: AwareDatetime
    status: Literal["SOURCE_BACKED", "CANDIDATE", "DISPUTED", "REVOKED", "STALE"]
    basis: Literal["SOURCE_REPORTED", "ISSUER_ATTRIBUTION", "CONDITIONAL_MECHANISM"]
    conditions: list[TEXT] = Field(default_factory=list, max_length=20)
    unknowns: list[TEXT] = Field(default_factory=list, max_length=20)
    direction: Literal["POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"] = "UNKNOWN"
    lag: TEXT = "UNKNOWN"
    evidence: list[Evidence] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def relation(self):
        if self.type not in RELATIONS or self.from_id == self.to_id:
            raise ValueError("Unknown relationship or self edge")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("Invalid validity window")
        if RELATIONS[self.type][0] == "MECHANISM" and not self.conditions:
            raise ValueError("Mechanisms require explicit conditions")
        return self


class Narrative(Strict):
    id: ID
    version: int = Field(ge=1)
    title: TEXT
    thesis: TEXT
    company_id: ID
    scope: TEXT
    horizon: TEXT
    watched_nodes: list[ID] = Field(min_length=1, max_length=30)
    assumptions: list[TEXT] = Field(min_length=1, max_length=20)
    supporting_evidence: list[TEXT] = Field(min_length=1, max_length=20)
    challenging_evidence: list[TEXT] = Field(min_length=1, max_length=20)
    reconsider_when: list[TEXT] = Field(min_length=1, max_length=20)
    unknowns: list[TEXT] = Field(min_length=1, max_length=20)
    # An empty list is allowed: related news can have no directional conclusion.
    challenge_event_types: list[ID] = Field(default_factory=list, max_length=30)
    support_event_types: list[ID] = Field(default_factory=list, max_length=30)
    available_at: AwareDatetime
    audience: Literal["SHARED_RESEARCH_EXAMPLE"] = "SHARED_RESEARCH_EXAMPLE"


class Event(Strict):
    id: ID
    version: int = Field(ge=1)
    type: ID
    headline: TEXT
    summary: TEXT
    anchors: list[ID] = Field(min_length=1, max_length=20)
    occurred_at: AwareDatetime
    available_at: AwareDatetime
    evidence: list[Evidence] = Field(min_length=1, max_length=20)
    historical: bool = True


class MetricObservation(Strict):
    id: ID
    node_id: ID
    value: Decimal = Field(allow_inf_nan=False)
    unit: TEXT
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    period_start: date
    period_end: date
    scope: TEXT
    basis: Literal["GAAP", "NON_GAAP", "PHYSICAL", "UNKNOWN"]
    evidence: list[Evidence] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def period(self):
        if self.period_start > self.period_end:
            raise ValueError("Invalid observation period")
        return self


class FactorBinding(Strict):
    """Curated literal topic/context/change groups, never a financial event classifier."""
    id: ID
    factor_id: ID
    topic_terms: list[TEXT] = Field(min_length=1, max_length=20)
    context_terms: list[TEXT] = Field(min_length=1, max_length=20)
    change_terms: list[TEXT] = Field(min_length=1, max_length=30)
    exclude_terms: list[TEXT] = Field(default_factory=list, max_length=20)
    term_aliases: dict[str, list[TEXT]] = Field(default_factory=dict, max_length=40)
    scope: TEXT
    reviewed_at: AwareDatetime
    review_until: AwareDatetime
    max_news_age_days: int = Field(default=14, ge=1, le=30)
    enabled: bool = True
    evidence: list[Evidence] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def bounded_rule(self):
        if not self.reviewed_at < self.review_until:
            raise ValueError("Binding review window invalid")
        if (self.review_until - self.reviewed_at).total_seconds() > 90 * 86400:
            raise ValueError("Binding must be rechecked within 90 days")
        terms = [*self.topic_terms, *self.context_terms, *self.change_terms, *self.exclude_terms]
        if not self.term_aliases.keys() <= set(terms):
            raise ValueError("Alias key must be an explicit binding term")
        for key, variants in self.term_aliases.items():
            if not 1 <= len(variants) <= 8 or len(set(v.casefold() for v in variants)) != len(variants):
                raise ValueError("Aliases must be unique and bounded")
            if any(v.casefold() == key.casefold() for v in variants):
                raise ValueError("Alias repeats canonical term")
        for term in [*terms, *(v for variants in self.term_aliases.values() for v in variants)]:
            if not 2 <= len(term.strip()) <= 80 or term != term.strip():
                raise ValueError("Invalid literal binding term")
        return self


class ProfileBundle(Strict):
    schema_version: Literal["company-profile-v1"] = "company-profile-v1"
    id: ID
    version: int = Field(ge=1)
    company_id: ID
    ticker: ID
    legal_name: TEXT
    identifiers: dict[str, str]
    snapshot_at: AwareDatetime
    available_at: AwareDatetime
    description: TEXT
    industry_modules: list[TEXT] = Field(min_length=1, max_length=10)
    sources: list[Source] = Field(min_length=1, max_length=30)
    components: list[Component] = Field(max_length=60)
    nodes: list[Node] = Field(min_length=1, max_length=200)
    relationships: list[Relationship] = Field(max_length=300)
    observations: list[MetricObservation] = Field(default_factory=list, max_length=200)
    factor_bindings: list[FactorBinding] = Field(default_factory=list, max_length=50)
    narratives: list[Narrative] = Field(default_factory=list, max_length=20)
    events: list[Event] = Field(default_factory=list, max_length=100)
    author_kind: Literal["AI_ASSISTED_SOURCE_EXTRACTION"] = "AI_ASSISTED_SOURCE_EXTRACTION"

    @model_validator(mode="after")
    def coherent(self):
        for rows, key in ((self.sources, "id"), (self.components, "key"), (self.nodes, "id"),
                          (self.relationships, "id"), (self.narratives, "id"), (self.events, "id"),
                          (self.observations, "id"), (self.factor_bindings, "id")):
            if len({getattr(r, key) for r in rows}) != len(rows):
                raise ValueError("Duplicate identity")
        nodes = {n.id: n for n in self.nodes}
        if self.company_id not in nodes or nodes[self.company_id].kind != "company":
            raise ValueError("Company node missing")
        if self.snapshot_at > self.available_at:
            raise ValueError("Snapshot cannot be later than availability")
        for s in self.sources:
            if s.retrieved_at > self.available_at or s.published_at > self.snapshot_at:
                raise ValueError("Future source or fabricated availability")
        for r in self.relationships:
            if r.from_id not in nodes or r.to_id not in nodes:
                raise ValueError("Dangling relation")
            _, start, end = RELATIONS[r.type]
            if nodes[r.from_id].kind not in start or nodes[r.to_id].kind not in end:
                raise ValueError("Relationship endpoint type mismatch")
            if r.known_at > self.available_at:
                raise ValueError("Future relation knowledge")
        for n in self.narratives:
            if n.company_id != self.company_id or not set(n.watched_nodes) <= nodes.keys():
                raise ValueError("Narrative scope mismatch")
            if n.available_at > self.available_at:
                raise ValueError("Future narrative")
        for e in self.events:
            if not set(e.anchors) <= nodes.keys() or e.occurred_at > self.snapshot_at:
                raise ValueError("Event scope/time mismatch")
            if e.available_at > self.available_at or e.occurred_at > e.available_at:
                raise ValueError("Future event")
        source_ids = {s.id for s in self.sources}
        for o in self.observations:
            if o.node_id not in nodes or nodes[o.node_id].kind != "metric":
                raise ValueError("Observation requires a metric node")
            if o.period_end > self.snapshot_at.date():
                raise ValueError("Future observation period")
        items: list[Component | Relationship | Event | MetricObservation | FactorBinding] = [
            *self.components, *self.relationships, *self.events, *self.observations,
            *self.factor_bindings]
        for item in items:
            if any(e.source_id not in source_ids for e in item.evidence):
                raise ValueError("Missing evidence source")
        sources = {s.id: s for s in self.sources}
        for binding in self.factor_bindings:
            if binding.factor_id not in nodes or nodes[binding.factor_id].kind not in {
                "factor", "input", "supplier", "market", "facility", "location"
            }:
                raise ValueError("Binding requires a scoped economic factor")
            if binding.reviewed_at > self.available_at or any(
                sources[e.source_id].retrieved_at > binding.reviewed_at for e in binding.evidence
            ):
                raise ValueError("Binding review must follow source capture and precede availability")
        for r in self.relationships:
            if any(sources[e.source_id].retrieved_at > r.known_at for e in r.evidence):
                raise ValueError("Relationship knowledge cannot predate captured evidence")
        for e in self.events:
            if any(sources[v.source_id].retrieved_at > e.available_at for v in e.evidence):
                raise ValueError("Event availability cannot predate captured evidence")
        return self


def source_text(blob):
    parser = Paragraphs()
    parser.feed(blob.decode("utf-8"))
    parser.flush()
    return "\n".join(parser.rows)


def load_bundle(directory):
    """Current pointer can revoke older versions; this is not immutable as-of replay."""
    receipt_path = directory / "current.json"
    if receipt_path.stat().st_size > 30_000:
        raise ValueError("Oversize pointer")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt["status"] != "active":
        raise ValueError("Withdrawn bundle")
    path = (directory / receipt["file"]).resolve()
    if not path.is_relative_to(directory.resolve()) or path.stat().st_size > 1_000_000:
        raise ValueError("Unsafe profile path")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("Profile version changed")
    bundle = ProfileBundle.model_validate_json(raw)
    if bundle.version != receipt["version"] or bundle.id != receipt["id"]:
        raise ValueError("Pointer identity mismatch")
    if bundle.available_at > datetime.now(UTC):
        raise ValueError("Future profile")
    verify_sources(directory, bundle)
    return bundle


def verify_sources(directory, bundle):
    texts = {}
    for s in bundle.sources:
        path = (directory / s.file).resolve()
        if not path.is_relative_to(directory.resolve()) or path.stat().st_size > 5_000_000:
            raise ValueError("Unsafe source path")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != s.sha256:
            raise ValueError("Source version changed")
        texts[s.id] = source_text(raw)
    items: list[Component | Relationship | Event | MetricObservation | FactorBinding] = [
        *bundle.components, *bundle.relationships, *bundle.events, *bundle.observations,
        *bundle.factor_bindings]
    for item in items:
        if any(e.quote not in texts[e.source_id] for e in item.evidence):
            raise ValueError("Evidence quote not in visible source")


@contextmanager
def writer_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / "writer.lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write("local profile writer")
    try:
        yield
    finally:
        lock.unlink()


def stage(directory, bundle):
    with writer_lock(directory):
        return stage_locked(directory, bundle)


def stage_locked(directory, bundle):
    """Local operator import; exclusive version file and atomic current pointer."""
    directory.mkdir(parents=True, exist_ok=True)
    pointer = directory / "current.json"
    previous = pointer.read_bytes() if pointer.exists() else None
    if previous:
        old = json.loads(previous)
        if old["id"] != bundle.id or bundle.version != old["version"] + 1:
            raise ValueError("Require next version of the same profile")
        if bundle.available_at <= load_bundle_version_time(directory, old):
            raise ValueError("New version requires later availability")
    elif bundle.version != 1:
        raise ValueError("First profile version must be one")
    if bundle.available_at > datetime.now(UTC):
        raise ValueError("Future profile")
    verify_sources(directory, bundle)
    name = f"profile-v{bundle.version}.json"
    raw = bundle.model_dump_json(indent=2).encode("utf-8")
    if len(raw) > 1_000_000:
        raise ValueError("Oversize profile")
    with (directory / name).open("xb") as stream:
        stream.write(raw)
    if (pointer.read_bytes() if pointer.exists() else None) != previous:
        raise ValueError("Concurrent pointer change; staged version not activated")
    receipt = {"id": bundle.id, "version": bundle.version, "file": name,
               "sha256": hashlib.sha256(raw).hexdigest(), "status": "active"}
    temporary = directory / ("current-v" + str(bundle.version) + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream)
    temporary.replace(pointer)
    return receipt


def load_bundle_version_time(directory, receipt):
    path = (directory / receipt["file"]).resolve()
    if not path.is_relative_to(directory.resolve()) or path.stat().st_size > 1_000_000:
        raise ValueError("Unsafe previous version")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("Previous version changed")
    return ProfileBundle.model_validate_json(raw).available_at


def withdraw(directory):
    with writer_lock(directory):
        pointer = directory / "current.json"
        receipt = json.loads(pointer.read_text(encoding="utf-8"))
        receipt["status"] = "withdrawn"
        temporary = directory / "withdraw.tmp"
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream)
        temporary.replace(pointer)


def paths(bundle, event, narrative, *, effective_at=None):
    """Directed simple routes: <=3 structural and <=2 mechanism edges, max5 total."""
    when = effective_at or bundle.snapshot_at
    edges = [r for r in bundle.relationships if r.status == "SOURCE_BACKED"
             and r.known_at <= bundle.available_at and r.valid_from <= when
             and (r.valid_until is None or when < r.valid_until)]
    # Company membership is established only by structural links, ignoring direction.
    connected = {bundle.company_id}
    for _ in range(len(bundle.nodes)):
        before = len(connected)
        for r in edges:
            if RELATIONS[r.type][0] == "STRUCTURAL" and {r.from_id, r.to_id} & connected:
                connected.update((r.from_id, r.to_id))
        if len(connected) == before:
            break
    queue: deque[tuple[str, list[Relationship], set[str], int, int]] = deque(
        (a, [], {a}, 0, 0) for a in event.anchors if a in connected)
    result: list[list[Relationship]] = []
    visits = 0
    while queue and len(result) < 20 and visits < 2000:
        node, route, seen, structural, mechanism = queue.popleft()
        visits += 1
        if node in narrative.watched_nodes:
            result.append(route)
            continue
        if len(route) >= 5:
            continue
        for r in edges:
            if r.from_id != node or r.to_id in seen:
                continue
            m = mechanism + int(RELATIONS[r.type][0] == "MECHANISM")
            s = structural + int(RELATIONS[r.type][0] == "STRUCTURAL")
            if m <= 2 and s <= 3:
                queue.append((r.to_id, route + [r], seen | {r.to_id}, s, m))
    return result, bool(queue)


def project(bundle):
    nodes = {n.id: n.label for n in bundle.nodes}
    cards = []
    for e in bundle.events:
        for n in bundle.narratives:
            routes, truncated = paths(bundle, e, n)
            if not routes:
                continue
            routes.sort(key=lambda route: (
                not any(RELATIONS[r.type][0] == "MECHANISM" for r in route), len(route)))
            route = routes[0]
            support, challenge = e.type in n.support_event_types, e.type in n.challenge_event_types
            stance = "MIXED" if support and challenge else (
                "SUPPORTS_ASSUMPTION" if support else "CHALLENGES_ASSUMPTION" if challenge
                else "RELATED_INFORMATION")
            if not any(RELATIONS[r.type][0] == "MECHANISM" for r in route):
                stance = "RELATED_INFORMATION"
            evidence = [*e.evidence, *(v for r in route for v in r.evidence)]
            cited = {v.source_id for v in evidence}
            cards.append({"id": f"{bundle.id}:{e.id}:{n.id}", "ticker": bundle.ticker,
                "headline": e.headline, "summary": e.summary, "historical": e.historical,
                "profile_version": bundle.version, "event_version": e.version,
                "narrative_version": n.version, "narrative": n.model_dump(mode="json"),
                "snapshot_at": bundle.snapshot_at.isoformat(),
                "available_at": bundle.available_at.isoformat(),
                "occurred_at": e.occurred_at.isoformat(), "stance": stance,
                "path": [{"id": r.id, "from": nodes[r.from_id], "to": nodes[r.to_id],
                          "type": r.type, "family": RELATIONS[r.type][0], "basis": r.basis,
                          "scope": r.scope, "conditions": r.conditions,
                          "evidence": [v.model_dump() for v in r.evidence]} for r in route],
                "unknowns": list(dict.fromkeys([*n.unknowns, *(u for r in route for u in r.unknowns)])),
                "sources": [{"id": s.id, "url": str(s.url), "sha256": s.sha256,
                             "published_at": s.published_at.isoformat()} for s in bundle.sources
                            if s.id in cited],
                "event_evidence": [v.model_dump() for v in e.evidence],
                "alternative_paths": len(routes) - 1, "paths_truncated": truncated,
                "decision_trace": ["Exact curated event anchors; no ticker keyword inference",
                    "Source-backed structural company connection",
                    "Directed bounded path at historical profile snapshot",
                    "Stance follows declared example narrative rule, not price prediction"],
                "delivery": "disabled", "price_impact": "UNKNOWN",
                "global_graph_approved": False, "author_kind": bundle.author_kind})
    present = {c.key: c for c in bundle.components}
    components = [present[k].model_dump(mode="json") if k in present else {
        "key": k, "status": "UNKNOWN", "summary": "Chưa thu thập bằng chứng", "evidence": []}
        for k in COMPONENTS]
    return {"id": bundle.id, "version": bundle.version, "ticker": bundle.ticker,
            "legal_name": bundle.legal_name, "identifiers": bundle.identifiers,
            "description": bundle.description, "industry_modules": bundle.industry_modules,
            "snapshot_at": bundle.snapshot_at.isoformat(), "components": components,
            "nodes": [n.model_dump() for n in bundle.nodes],
            "relationships": [r.model_dump(mode="json") for r in bundle.relationships],
            "observations": [o.model_dump(mode="json") for o in bundle.observations],
            "factor_bindings": [b.model_dump(mode="json") for b in bundle.factor_bindings],
            "sources": [{"id": s.id, "url": str(s.url), "sha256": s.sha256,
                         "published_at": s.published_at.isoformat(),
                         "retrieved_at": s.retrieved_at.isoformat()} for s in bundle.sources],
            "cards": cards, "coverage": dict((s, sum(c["status"] == s for c in components))
                for s in {c["status"] for c in components}),
            "narratives": [n.model_dump(mode="json") for n in bundle.narratives]}


def available_bundles(as_of=None):
    at = as_of or datetime.now(UTC)
    if at.tzinfo is None:
        raise ValueError("Aware cutoff required")
    if not Settings.from_env().dev_informational_feed:
        return {"items": [], "enabled": False, "delivery": "disabled"}
    root = Path(os.getenv("COMPANY_PROFILE_ROOT", "source-cache/company-profiles"))
    directories = sorted(p for p in root.glob("*") if p.is_dir())
    items, withheld = [], 0
    for directory in directories[:30]:
        try:
            if not directory.resolve().is_relative_to(root.resolve()):
                raise ValueError("Profile directory outside root")
            b = load_bundle(directory)
            if b.available_at <= at:
                items.append(b)
        except (OSError, ValueError, KeyError, TypeError):
            withheld += 1
    counts = Counter(item.id for item in items)
    duplicates = {id for id, n in counts.items() if n > 1}
    withheld += sum(item.id in duplicates for item in items)
    items = [item for item in items if item.id not in duplicates]
    return {"items": items, "enabled": True, "as_of": at.isoformat(),
            "withheld": withheld, "truncated": len(directories) > 30,
            "component_catalog": COMPONENTS, "delivery": "disabled"}


def feed(as_of=None):
    result = available_bundles(as_of)
    return {**result, "items": [project(b) for b in result["items"]]}


def framework():
    return {"version": "company-profile-v1", "components": COMPONENTS,
            "relationships": {k: {"family": v[0], "from_kinds": sorted(v[1]),
                                   "to_kinds": sorted(v[2])} for k, v in RELATIONS.items()},
            "schema": ProfileBundle.model_json_schema(), "delivery": "disabled"}


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["schema", "validate", "stage", "withdraw"])
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.action == "schema":
        print(json.dumps(framework(), ensure_ascii=False, indent=2))
    elif args.action == "stage" and args.directory and args.input:
        print(json.dumps(stage(args.directory, ProfileBundle.model_validate_json(
            args.input.read_bytes()))))
    elif args.action == "withdraw" and args.directory:
        withdraw(args.directory)
        print(json.dumps({"status": "withdrawn", "delivery": "disabled"}))
    elif args.directory:
        if args.action != "validate":
            parser.error("stage requires --input")
        bundle = load_bundle(args.directory)
        print(json.dumps({"valid": True, "version": bundle.version,
                          "cards": len(project(bundle)["cards"]), "delivery": "disabled"}))
    else:
        parser.error("--directory required for validation")


if __name__ == "__main__":
    main()
