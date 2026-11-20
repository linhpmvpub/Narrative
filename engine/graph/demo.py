"""Explicit, immutable synthetic context; production candidate rows are never promoted."""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from engine.graph.matcher import Edge
from engine.ingestion.contracts import digest
from engine.models.schema_v3 import demo_contexts, metadata
from engine.scoring.policy import NarrativeInput
from engine.seed import identifier, read_config


def require_demo(conn: Connection) -> None:
    mode = metadata.tables["rie_database_mode"]
    if conn.execute(select(mode.c.mode).where(mode.c.id == 1)).scalar_one_or_none() != "synthetic":
        raise ValueError("Demo graph requires isolated synthetic database")


def install_context(engine: Engine, config: Path, graph_file: Path, policy_file: Path) -> str:
    seeds = read_config(config)
    graph = json.loads(graph_file.read_text(encoding="utf-8"))
    policy = json.loads(policy_file.read_text(encoding="utf-8"))
    if any(
        x.get("is_synthetic") is not True or x.get("never_use_in_live") is not True
        for x in (graph, policy)
    ):
        raise ValueError("Synthetic context stamps required")
    available = datetime.fromisoformat(policy["simulated_available_at"].replace("Z", "+00:00"))
    if available.tzinfo is None:
        raise ValueError("Context requires aware simulated timestamp")
    graph_available = datetime.fromisoformat(graph["as_of_available_at"].replace("Z", "+00:00"))
    if graph_available.tzinfo is None:
        raise ValueError("Graph snapshot requires aware availability")
    available = max(available, graph_available)
    edges_by_id = {e.relation_id: e for e in seeds["relationships"]}
    if len(graph["edges"]) != 40 or {e["relation_id"] for e in graph["edges"]} != set(edges_by_id):
        raise ValueError("Demo graph must cover each candidate edge exactly once")
    edges = []
    for approval in graph["edges"]:
        base = edges_by_id[approval["relation_id"]]
        if (
            approval["is_synthetic"] is not True
            or approval["status"] != "verified"
            or approval["evidence_uri"] != f"fixture://synthetic/evidence/{base.relation_id}"
        ):
            raise ValueError("Invalid synthetic approval evidence")
        edges.append(
            Edge(
                id=base.relation_id,
                from_entity=base.from_entity,
                to_entity=base.to_entity,
                family=base.family,
                mechanism=base.mechanism,
                status="verified",
                sign=base.sign,
                strength=approval["strength"],
                confidence=approval["confidence"],
                recorded_at=approval["available_at"],
                valid_from=approval["verified_at"],
                reviewed_at=approval["verified_at"],
                reviewer="synthetic-fixture-reviewer",
                evidence_urls=(approval["evidence_uri"],),
                evidence_available_at=approval["available_at"],
                conditions=tuple(policy["edge_conditions"].get(base.relation_id, [])),
                is_synthetic=True,
            )
        )
    nodes = {e.entity_id for e in seeds["entities"]}
    narratives = []
    for n in seeds["narratives"]:
        outcomes = policy["outcomes"][n.narrative_id]
        if not set(outcomes) <= nodes or not all(
            x.startswith(n.primary_ticker + "_") for x in outcomes
        ):
            raise ValueError("Narrative outcome must belong to its company")
        narratives.append(
            NarrativeInput(
                id=n.narrative_id,
                version_id=f"synthetic:{n.narrative_id}:v{n.version}",
                ticker=n.primary_ticker,
                available_at=available,
                outcomes=outcomes,
                hypothesis_polarity=n.hypothesis_polarity_for_company,
                watch_next=n.disconfirmation,
                is_synthetic=True,
            ).model_dump(mode="json")
        )
    payload = {
        "is_synthetic": True,
        "nodes": sorted(nodes),
        "edges": [e.model_dump(mode="json") for e in edges],
        "narratives": narratives,
        "policy": policy,
        "graph_source_sha256": digest(graph),
    }
    checksum = digest(payload)
    context_id = "demo-" + checksum
    with engine.begin() as conn:
        require_demo(conn)
        if conn.execute(select(demo_contexts.c.id).where(demo_contexts.c.id == context_id)).first():
            return context_id
        conn.execute(
            demo_contexts.insert().values(
                id=context_id, available_at=available, payload=payload, sha256=checksum
            )
        )
        sources, docs, evidence = (
            metadata.tables[n] for n in ("rie_sources", "rie_documents", "rie_evidence")
        )
        if (
            conn.execute(select(sources.c.id).where(sources.c.id == "synthetic-graph")).first()
            is None
        ):
            conn.execute(
                sources.insert().values(
                    id="synthetic-graph",
                    name="SYNTHETIC graph evidence",
                    origin="fixture",
                    rights_status="blocked",
                    citation_url="fixture://synthetic/evidence",
                    rights_note="Demo-only simulated approvals, prohibited in live processing",
                )
            )
        for edge in edges:
            doc_id = identifier(context_id + ":doc:" + edge.id)
            conn.execute(
                docs.insert().values(
                    id=doc_id,
                    source_id="synthetic-graph",
                    source_url=edge.evidence_urls[0],
                    content_sha256=digest(
                        {"context": context_id, "edge": edge.model_dump(mode="json")}
                    ),
                    title="SYNTHETIC mechanism " + edge.id,
                    published_at=edge.evidence_available_at,
                    first_seen_at=edge.evidence_available_at,
                    available_at=edge.evidence_available_at,
                    is_synthetic=True,
                    metadata={
                        "context_id": context_id,
                        "edge": edge.model_dump(mode="json"),
                        "simulation_only": True,
                    },
                )
            )
            conn.execute(
                evidence.insert().values(
                    id=identifier(context_id + ":evidence:" + edge.id),
                    document_id=doc_id,
                    text_start=0,
                    text_end=len(edge.mechanism),
                    quoted_claim=edge.mechanism,
                    url=edge.evidence_urls[0],
                    verified_by="synthetic-fixture-reviewer",
                    verified_at=edge.reviewed_at,
                )
            )
    return context_id


def load_context(conn: Connection, context_id: str, as_of: datetime) -> dict:
    if as_of.tzinfo is None:
        raise ValueError("Timezone-aware as_of required")
    require_demo(conn)
    row = (
        conn.execute(
            select(demo_contexts).where(
                demo_contexts.c.id == context_id, demo_contexts.c.available_at <= as_of
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ValueError("Synthetic context unavailable at as_of")
    if digest(row["payload"]) != row["sha256"]:
        raise ValueError("Context was mutated")
    return row["payload"]
