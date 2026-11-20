"""Bounded graph traversal over point-in-time, evidence-backed edge snapshots."""

from datetime import datetime
from math import prod
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.engine import Connection

from engine.graph.review import check_evidence
from engine.models.contracts import utc
from engine.models.schema_v1 import metadata


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    id: str
    from_entity: str
    to_entity: str
    family: str
    mechanism: str
    status: Literal["candidate", "verified", "rejected", "stale"]
    sign: Literal["positive", "negative", "conditional", "unknown"]
    strength: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    recorded_at: AwareDatetime
    valid_from: AwareDatetime | None
    valid_until: AwareDatetime | None = None
    reviewed_at: AwareDatetime | None
    reviewer: str | None
    evidence_urls: tuple[str, ...] = ()
    evidence_available_at: AwareDatetime | None
    conditions: tuple[str, ...] = ()
    is_synthetic: bool = False

    def eligible(self, as_of: datetime, synthetic: bool) -> bool:
        return bool(
            self.status == "verified"
            and self.reviewer
            and self.evidence_urls
            and self.is_synthetic == synthetic
            and self.strength is not None
            and all(
                t is not None and t <= as_of
                for t in (
                    self.recorded_at,
                    self.valid_from,
                    self.reviewed_at,
                    self.evidence_available_at,
                )
            )
            and (self.valid_until is None or as_of < self.valid_until)
        )


class PathResult(BaseModel):
    edges: list[Edge]
    target: str
    relevance: float
    confidence: float
    sign: str
    conditional_reasons: list[str]
    exposure: None = None
    sensitivity: None = None
    strength_basis: str = "Routing heuristic; exposure and sensitivity are unknown"


def match_paths(
    edges: list[Edge],
    *,
    nodes: set[str],
    start: str,
    targets: set[str],
    as_of: datetime,
    source_confidence: float,
    synthetic: bool,
    max_hops: int = 2,
) -> list[PathResult]:
    if as_of.tzinfo is None or not 0 <= max_hops <= 2 or not 0 <= source_confidence <= 1:
        raise ValueError("Aware as_of, 0–2 hops and valid confidence required")
    if (
        start not in nodes
        or not targets <= nodes
        or any(e.from_entity not in nodes or e.to_entity not in nodes for e in edges)
    ):
        raise ValueError("Unknown graph entity")
    if len({e.id for e in edges}) != len(edges):
        raise ValueError("Resolve edge versions before matching")
    adjacency: dict[str, list[Edge]] = {}
    for edge in edges:
        if edge.eligible(as_of, synthetic):
            adjacency.setdefault(edge.from_entity, []).append(edge)
    paths: list[PathResult] = []

    def visit(node: str, path: list[Edge], seen: set[str]) -> None:
        if node in targets:
            signs = [e.sign for e in path]
            sign = (
                "unknown"
                if "unknown" in signs
                else "conditional"
                if "conditional" in signs
                else "negative"
                if signs.count("negative") % 2
                else "positive"
            )
            conditions = sorted(
                {c for e in path for c in e.conditions}
                | {
                    f"direction_unresolved:{e.id}"
                    for e in path
                    if e.sign in ("conditional", "unknown")
                }
            )
            paths.append(
                PathResult(
                    edges=path,
                    target=node,
                    relevance=prod(float(e.strength or 0) for e in path)
                    * (0.85 ** max(0, len(path) - 1)),
                    confidence=min([source_confidence] + [e.confidence for e in path]),
                    sign=sign,
                    conditional_reasons=conditions,
                )
            )
        if len(path) == max_hops:
            return
        for edge in sorted(adjacency.get(node, []), key=lambda x: x.id):
            if edge.to_entity not in seen:
                visit(edge.to_entity, path + [edge], seen | {edge.to_entity})

    visit(start, [], {start})
    return sorted(
        paths,
        key=lambda p: (
            -p.relevance,
            -p.confidence,
            len(p.edges),
            tuple(e.id for e in p.edges),
            p.target,
        ),
    )


def live_edges_as_of(conn: Connection, as_of: datetime) -> list[Edge]:
    """Never trust mutable edge status without an audited approval snapshot."""
    if as_of.tzinfo is None:
        raise ValueError("Timezone-aware as_of required")
    revisions = metadata.tables["rie_relationship_revisions"]
    latest = {}
    for row in conn.execute(
        select(revisions)
        .where(revisions.c.changed_at <= as_of)
        .order_by(revisions.c.changed_at, revisions.c.id)
    ).mappings():
        latest[row["relationship_id"]] = row
    result = []
    for row in latest.values():
        data = row["after"]
        if data.get("status") != "verified":
            continue
        ids = data.get("metadata", {}).get("evidence_ids", [])
        try:
            check_evidence(conn, ids, as_of)
        except ValueError:
            continue
        ev = metadata.tables["rie_evidence"]
        urls = tuple(conn.execute(select(ev.c.url).where(ev.c.id.in_(ids))).scalars())
        result.append(
            Edge(
                id=data["id"],
                from_entity=data["from_entity_id"],
                to_entity=data["to_entity_id"],
                family=data["relation_family"],
                mechanism=data["mechanism"],
                status=data["status"],
                sign=data["sign"],
                strength=data["strength"],
                confidence=data["confidence"],
                recorded_at=max(
                    datetime.fromisoformat(data["recorded_at"]), utc(row["changed_at"])
                ),
                valid_from=data["valid_from"],
                valid_until=data["valid_until"],
                reviewed_at=data["verified_at"],
                reviewer=data["verified_by"],
                evidence_urls=urls,
                evidence_available_at=utc(row["changed_at"]),
                conditions=tuple(data.get("metadata", {}).get("conditions", [])),
            )
        )
    return result
