"""Inspectable graph snapshots and bounded hypothetical scenarios, no price forecasts."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, Field
from sqlalchemy import select

from engine.api.product import Body, User
from engine.db import database
from engine.graph.matcher import Edge, live_edges_as_of, match_paths
from engine.models.contracts import utc
from engine.models.schema_v7 import metadata
from engine.settings import Settings

router = APIRouter(prefix="/api/v0/impact-map", tags=["Relationship and impact diagnostics"])
Ticker = Literal["MU", "NVDA", "AMD", "DELL", "SNDK"]


def demo_graph():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "web/map-demo.json").read_text(encoding="utf-8")
    )


def graph_snapshot(conn, cutoff):
    nodes = [dict(r) for r in conn.execute(select(metadata.tables["rie_entities"])).mappings()]
    nodes = [{"id": r["id"], "label": r["display_name"], "type": r["entity_type"]} for r in nodes]
    initial = json.loads(
        (Path(__file__).resolve().parents[1] / "web/map-seed.json").read_text(encoding="utf-8")
    )
    edges = {
        r["relation_id"]: {
            "id": r["relation_id"],
            "from_entity": r["from_entity"],
            "to_entity": r["to_entity"],
            "family": r["family"],
            "mechanism": r["mechanism"],
            "sign": r["sign"],
            "status": "candidate",
            "strength": None,
            "confidence": None,
            "conditions": [],
            "evidence_urls": [],
            "eligible": False,
            "reason": "No audited evidence-backed approval",
        }
        for r in initial
        if datetime.fromisoformat(r["recorded_at"].replace("Z", "+00:00")) <= cutoff
    }
    revisions = metadata.tables["rie_relationship_revisions"]
    for row in conn.execute(
        select(revisions)
        .where(revisions.c.changed_at <= cutoff)
        .order_by(revisions.c.changed_at, revisions.c.id)
    ).mappings():
        d = row["after"]
        if d["id"] in edges:
            edges[d["id"]].update(
                status=d["status"],
                mechanism=d["mechanism"],
                sign=d["sign"],
                reason="Approval not eligible at this timestamp",
            )
    audited = live_edges_as_of(conn, cutoff)
    for edge in audited:
        if edge.id in edges:
            eligible = edge.eligible(cutoff, False)
            edges[edge.id] = {
                **edge.model_dump(mode="json"),
                "eligible": eligible,
                "reason": "Audited evidence" if eligible else "Temporal/evidence gate failed",
            }
    return {
        "nodes": nodes,
        "edges": list(edges.values()),
        "is_synthetic": False,
        "as_of": cutoff.isoformat(),
        "delivery": "disabled",
        "price_impact": "UNKNOWN",
    }, audited


def scenario(graph, edges, ticker, start, direction, cutoff, synthetic):
    nodes = {n["id"] for n in graph["nodes"]}
    targets = {
        n["id"]
        for n in graph["nodes"]
        if n["type"] == "financial_metric" and n["id"].startswith(ticker + "_")
    }
    if start not in nodes:
        raise HTTPException(422, "Unknown driver/entity")
    paths = match_paths(
        edges,
        nodes=nodes,
        start=start,
        targets=targets,
        as_of=cutoff,
        source_confidence=1.0,
        synthetic=synthetic,
        max_hops=2,
    )
    rendered = []
    for path in paths:
        effect = "UNRESOLVED"
        if path.sign in {"positive", "negative"}:
            sign = direction * (1 if path.sign == "positive" else -1)
            effect = "INCREASE" if sign > 0 else "DECREASE"
            if path.conditional_reasons:
                effect = "CONDITIONAL_" + effect
        rendered.append({**path.model_dump(mode="json"), "hypothetical_metric_direction": effect})
    return {
        "mode": "hypothetical_scenario",
        "is_synthetic": synthetic,
        "ticker": ticker,
        "start": start,
        "assumed_direction": direction,
        "as_of": cutoff.isoformat(),
        "paths": rendered,
        "price_impact": "UNKNOWN",
        "materiality": "UNKNOWN",
        "confidence_meaning": "Minimum heuristic edge confidence; not calibrated probability",
        "relevance_formula": "product(edge strength) * 0.85^(hops-1)",
        "reason": None if paths else "No eligible directed path within two hops",
        "delivery": "disabled",
    }


class ScenarioBody(Body):
    ticker: Ticker = "DELL"
    start: str = Field(default="NAND_ASP", min_length=1, max_length=100)
    direction: Literal[-1, 1] = 1
    as_of: AwareDatetime | None = None


@router.get("/demo")
def demo_snapshot(as_of: datetime | None = None):
    graph = demo_graph()
    cutoff = as_of or datetime.fromisoformat(graph["as_of"])
    if cutoff.tzinfo is None:
        raise HTTPException(422, "Aware as_of required")
    graph["edges"] = [
        {
            **e,
            "eligible": Edge.model_validate(e).eligible(cutoff, True),
            "reason": "Synthetic evidence; eligibility evaluated at selected as_of",
        }
        for e in graph["edges"]
    ]
    if datetime.fromisoformat(graph["sample"]["decision_trace"]["as_of"]) > cutoff:
        graph["sample"] = None
    graph["as_of"] = cutoff.isoformat()
    return graph


@router.post("/demo-scenario")
def demo_scenario(body: ScenarioBody):
    graph = demo_graph()
    cutoff = body.as_of or datetime.fromisoformat(graph["as_of"])
    return scenario(
        graph,
        [Edge.model_validate(e) for e in graph["edges"]],
        body.ticker,
        body.start,
        body.direction,
        cutoff,
        True,
    )


@router.get("")
def live_map(user: User, as_of: datetime | None = None):
    cutoff = as_of or datetime.now(UTC)
    if cutoff.tzinfo is None or cutoff > datetime.now(UTC):
        raise HTTPException(422, "Aware nonfuture as_of required")
    engine = database()
    try:
        with engine.connect() as conn:
            graph, _ = graph_snapshot(conn, cutoff)
            graph["notices"] = []
            if Settings.from_env().dev_informational_feed:
                cards, links, ev = (
                    metadata.tables[n]
                    for n in ("rie_user_cards", "rie_card_threads", "rie_event_versions")
                )
                visible = (
                    select(links.c.card_id)
                    .where(links.c.card_id == cards.c.id, links.c.available_at <= cutoff)
                    .exists()
                )
                rows = conn.execute(
                    select(
                        cards.c.id,
                        ev.c.event_id,
                        ev.c.version_number,
                        ev.c.factual_headline,
                        ev.c.normalized_claim,
                        ev.c.available_at,
                    )
                    .join(ev, cards.c.event_version_id == ev.c.id)
                    .where(cards.c.user_id == user.id, visible, ev.c.available_at <= cutoff)
                    .order_by(ev.c.available_at.desc(), ev.c.version_number.desc())
                    .limit(500)
                ).mappings()
                seen = set()
                for r in rows:
                    if (
                        r["event_id"] in seen
                        or r["normalized_claim"].get("mode") != "development_sec_notice"
                    ):
                        continue
                    seen.add(r["event_id"])
                    # Invalidate stale projections even before the next owner refresh.
                    current = (
                        conn.execute(
                            select(ev)
                            .where(ev.c.event_id == r["event_id"], ev.c.available_at <= cutoff)
                            .order_by(ev.c.version_number.desc())
                            .limit(1)
                        )
                        .mappings()
                        .one()
                    )
                    claim = current["normalized_claim"]
                    graph["notices"].append(
                        {
                            "id": r["id"],
                            "ticker": claim["ticker"],
                            "headline": current["factual_headline"],
                            "version": current["version_number"],
                            "available_at": utc(current["available_at"]).isoformat(),
                            "source_status": claim.get("source_status", "active"),
                            "url": claim["url"],
                            "economic_observations": [],
                            "impact": "INSUFFICIENT_EVIDENCE",
                            "reason": "Filing metadata alone does not establish a directional economic observation",
                        }
                    )
            return graph
    finally:
        engine.dispose()


@router.post("/scenario")
def live_scenario(body: ScenarioBody, user: User):
    cutoff = body.as_of or datetime.now(UTC)
    if cutoff > datetime.now(UTC):
        raise HTTPException(422, "Future as_of is not a live snapshot")
    engine = database()
    try:
        with engine.connect() as conn:
            graph, edges = graph_snapshot(conn, cutoff)
            return scenario(graph, edges, body.ticker, body.start, body.direction, cutoff, False)
    finally:
        engine.dispose()
