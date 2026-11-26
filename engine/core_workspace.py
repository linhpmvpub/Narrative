"""Local compact core view. Rebuild from current evidence; never load cached cards."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.commodity_context import Observation, evaluate_registry
from engine.core_profile import project
from engine.impact_atlas import read_snapshot
from engine.ingestion.contracts import digest
from engine.input_markets import read, route
from engine.scope_review import Store


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    mode: Literal["RSS_CURRENT", "MANUAL_RESEARCH", "SYNTHETIC"]
    observation: str
    selection: str
    articles: str
    store: str
    market_id: str | None = None


class Workspace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    atlas: str
    registry: str
    events: list[Event] = Field(default_factory=list, max_length=100)


def local_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Workspace paths must remain inside the local workspace")
    return path


def bundle(event_id, mode, cards):
    """Bundle only identical event revisions/measurements; preserve every product path."""
    groups = {}
    for card in cards:
        common = {
            k: v
            for k, v in card.items()
            if k
            not in {
                "product",
                "scope",
                "usage_relation_id",
                "usage_evidence",
                "usage_source_urls",
                "narrative_ids",
                "price_markets",
            }
        }
        key = digest({"event_id": event_id, "mode": mode, "common": common})
        if key not in groups:
            groups[key] = {
                **common,
                "id": key,
                "event_id": event_id,
                "mode": mode,
                "products": [],
                "narrative_ids": [],
            }
        product = {
            k: card[k]
            for k in (
                "product",
                "scope",
                "usage_relation_id",
                "usage_evidence",
                "usage_source_urls",
                "price_markets",
            )
        }
        if product not in groups[key]["products"]:
            groups[key]["products"].append(product)
        groups[key]["narrative_ids"] = sorted(
            set(groups[key]["narrative_ids"] + card["narrative_ids"])
        )
    return list(groups.values())


def build(manifest, *, include_synthetic=False, news_conn=None):
    manifest = Path(manifest)
    raw = manifest.read_bytes()
    config = Workspace.model_validate_json(raw)
    if len({e.id for e in config.events}) != len(config.events):
        raise ValueError("Duplicate event identifiers")
    root = manifest.parent

    def path(value):
        return local_path(root, value)

    data = read_snapshot(path(config.atlas))
    registry = read(path(config.registry), data)
    core = project(data, registry)
    paths = [row for c in registry.commodities for row in route(registry, c.id)]
    cards, held = [], []
    for event in config.events:
        if event.mode == "SYNTHETIC" and not include_synthetic:
            continue
        if event.mode == "RSS_CURRENT" and news_conn is None:
            raise ValueError("RSS current-state connection required")
        try:
            result = evaluate_registry(
                data,
                Observation.model_validate_json(path(event.observation).read_bytes()),
                json.loads(path(event.selection).read_bytes()),
                path(config.registry),
                market_id=event.market_id,
                store=Store(path(event.store)),
                article_root=path(event.articles),
                news_conn=news_conn if event.mode == "RSS_CURRENT" else None,
            )
            cards.extend(bundle(event.id, event.mode, result["candidate_alerts"]))
            if not result["candidate_alerts"]:
                held.append({"event_id": event.id, "reason": "NO_CURRENT_ELIGIBLE_PATH"})
        except (ValueError, OSError, KeyError):
            held.append({"event_id": event.id, "reason": "EVIDENCE_UNAVAILABLE_OR_INVALID"})
    # Detect a configuration/registry swap while building a response.
    if (
        manifest.read_bytes() != raw
        or read(path(config.registry), data) != registry
        or digest(read_snapshot(path(config.atlas))) != digest(data)
    ):
        raise ValueError("Workspace changed during refresh")
    return {
        "core": core,
        "paths": paths,
        "commodities": [c.model_dump(mode="json") for c in registry.commodities],
        "sources": [{"id": s.id, "url": str(s.url), "status": s.status} for s in registry.sources],
        "cards": cards,
        "held": held,
        "delivery": "disabled",
        "financial_magnitude": "UNKNOWN",
        "synthetic_included": include_synthetic,
    }
