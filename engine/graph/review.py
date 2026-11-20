import json
from contextlib import nullcontext
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from engine.models.contracts import utc
from engine.models.schema_v1 import metadata


def snapshot(row) -> dict:
    return json.loads(json.dumps(dict(row), default=str))


def check_evidence(conn: Connection, ids: list[str], at: datetime) -> None:
    if not ids:
        raise ValueError("Evidence is required")
    e, d, s = (metadata.tables[name] for name in ("rie_evidence", "rie_documents", "rie_sources"))
    for evidence_id in ids:
        row = (
            conn.execute(
                select(
                    e.c.url,
                    e.c.verified_by,
                    e.c.verified_at,
                    e.c.created_at,
                    e.c.text_start,
                    e.c.text_end,
                    e.c.quoted_claim,
                    d.c.source_url,
                    d.c.published_at,
                    d.c.first_seen_at,
                    d.c.available_at,
                    d.c.retrieved_at,
                    d.c.is_synthetic,
                    s.c.rights_status,
                )
                .select_from(e.join(d).join(s))
                .where(e.c.id == evidence_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None or row["is_synthetic"] or row["rights_status"] != "approved":
            raise ValueError("Evidence must reference an approved non-synthetic document")
        url = urlparse(row["url"])
        if url.scheme != "https" or not url.netloc or row["url"] != row["source_url"]:
            raise ValueError("Evidence citation must match its HTTPS document URL")
        if (
            not (row["verified_by"] or "").strip()
            or not row["quoted_claim"].strip()
            or row["text_start"] is None
            or row["text_end"] is None
            or not 0 <= row["text_start"] < row["text_end"]
        ):
            raise ValueError("Reviewed claim and source offsets required")
        for field in (
            "verified_at",
            "created_at",
            "published_at",
            "first_seen_at",
            "available_at",
            "retrieved_at",
        ):
            if row[field] is None or utc(row[field]) > at:
                raise ValueError("Evidence unavailable at review time")


def approve_relationship(
    engine: Engine | Connection,
    relation_id: str,
    *,
    evidence_ids: list[str],
    reviewer: str,
    reason: str,
    reviewed_at: datetime,
    valid_from: datetime,
    strength: Decimal,
    confidence: Decimal,
    routing_basis: str,
    conditions: tuple[str, ...] = (),
) -> None:
    if reviewed_at.tzinfo is None or valid_from.tzinfo is None:
        raise ValueError("Timezone-aware review timestamps required")
    if not reviewer.strip() or not reason.strip() or not routing_basis.strip():
        raise ValueError("Reviewer, reason and qualitative routing basis required")
    if not 0 <= strength <= 1 or not 0 <= confidence <= 1 or valid_from > reviewed_at:
        raise ValueError("Invalid review values")
    recorded_at = datetime.now(UTC)
    if reviewed_at > recorded_at:
        raise ValueError("Review cannot be future dated")
    edges, links, revisions = (
        metadata.tables[name]
        for name in ("rie_relationships", "rie_relationship_evidence", "rie_relationship_revisions")
    )
    with nullcontext(engine) if isinstance(engine, Connection) else engine.begin() as conn:
        before = (
            conn.execute(select(edges).where(edges.c.id == relation_id).with_for_update())
            .mappings()
            .one()
        )
        if before["status"] != "candidate" or utc(before["recorded_at"]) > reviewed_at:
            raise ValueError("Review requires an available candidate")
        check_evidence(conn, evidence_ids, reviewed_at)
        required_conditions = set(conditions)
        if (
            before["from_entity_id"] in ("DRAM_ASP", "NAND_ASP")
            and before["to_entity_id"] == "SERVER_COMPONENT_COST"
        ):
            required_conditions.add("contracted_cost_rises")
        if (
            before["from_entity_id"] == "SERVER_COMPONENT_COST"
            and before["to_entity_id"] == "DELL_ISG_MARGIN"
        ):
            required_conditions.add("cost_not_offset")
        values = {
            "status": "verified",
            "verified_at": reviewed_at,
            "verified_by": reviewer,
            "valid_from": valid_from,
            "recorded_at": recorded_at,
            "strength": strength,
            "confidence": confidence,
            "metadata": {
                **before["metadata"],
                "routing_basis": routing_basis,
                "evidence_ids": sorted(set(evidence_ids)),
                "conditions": sorted(required_conditions),
            },
        }
        conn.execute(edges.update().where(edges.c.id == relation_id).values(**values))
        for evidence_id in set(evidence_ids):
            conn.execute(
                links.insert().values(relationship_id=relation_id, evidence_id=evidence_id)
            )
        conn.execute(
            revisions.insert().values(
                id=str(uuid4()),
                relationship_id=relation_id,
                before=snapshot(before),
                after=snapshot({**before, **values}),
                reviewer_id=reviewer,
                reason=reason,
                changed_at=recorded_at,
            )
        )


def live_edge_eligible(conn: Connection, relation_id: str, as_of: datetime) -> bool:
    from engine.graph.matcher import live_edges_as_of

    return any(
        edge.id == relation_id and edge.eligible(as_of, False)
        for edge in live_edges_as_of(conn, as_of)
    )
