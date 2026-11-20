"""Validate the entire seed package before writing; never import demo approvals."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypedDict
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.engine import Engine

from engine.db import database
from engine.models.contracts import Entity, Narrative, Relationship, Stock
from engine.models.schema_v1 import metadata


def identifier(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, "threadnote-rie:" + value))


class SeedData(TypedDict):
    entities: list[Entity]
    stocks: list[Stock]
    narratives: list[Narrative]
    relationships: list[Relationship]


def read_config(path: Path) -> SeedData:
    def read(name: str) -> list[dict]:
        return json.loads((path / f"{name}.json").read_text(encoding="utf-8"))

    data: SeedData = {
        "entities": [Entity.model_validate(x) for x in read("entities")],
        "stocks": [Stock.model_validate(x) for x in read("stocks")],
        "narratives": [Narrative.model_validate(x) for x in read("narratives")],
        "relationships": [Relationship.model_validate(x) for x in read("relationships")],
    }

    def unique(items: list, key: str) -> None:
        ids = [getattr(item, key) for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate {key}")

    unique(data["entities"], "entity_id")
    unique(data["stocks"], "ticker")
    unique(data["narratives"], "narrative_id")
    unique(data["relationships"], "relation_id")
    nodes = {item.entity_id: item for item in data["entities"]}
    stocks = data["stocks"]
    if len(stocks) != 5 or {item.ticker for item in stocks} != {
        "MU",
        "NVDA",
        "AMD",
        "DELL",
        "SNDK",
    }:
        raise ValueError("Expected exactly five pilot stocks")
    if {x.entity_id for x in data["entities"] if x.entity_type == "company"} != {
        x.entity_id for x in stocks
    }:
        raise ValueError("Company registry differs from five pilot identities")
    for stock in stocks:
        if nodes[stock.entity_id].current_ticker != stock.ticker:
            raise ValueError("Ticker/entity mismatch")
    if Counter(item.primary_ticker for item in data["narratives"]) != Counter(
        {x.ticker: 2 for x in stocks}
    ):
        raise ValueError("Expected ten narratives, two per ticker")
    for narrative in data["narratives"]:
        if not set(narrative.driver_ids + narrative.watch_entities) <= nodes.keys():
            raise ValueError("Unknown narrative node")
    if len(data["relationships"]) != 40:
        raise ValueError("Expected forty candidate edges")
    for edge in data["relationships"]:
        if edge.from_entity not in nodes or edge.to_entity not in nodes:
            raise ValueError("Unknown graph node")
        if (
            edge.status != "candidate"
            or edge.strength is not None
            or edge.confidence != 0
            or edge.evidence_ids
        ):
            raise ValueError("Seed may only import unverified candidate edges")
    return data


def seed(engine: Engine, path: Path) -> dict:
    data = read_config(path)
    # The package has no historical narrative timestamps. Record actual import time,
    # never backdate templates to make an October replay appear to work.
    now = datetime.now(UTC)
    entities = metadata.tables["rie_entities"]
    with engine.begin() as conn:

        def insert_once(table_name: str, values: dict) -> None:
            table = metadata.tables[table_name]
            predicate = [table.c[col.name] == values[col.name] for col in table.primary_key]
            if conn.execute(select(table).where(*predicate)).first() is None:
                conn.execute(table.insert().values(**values))

        for item in data["entities"]:
            payload = item.model_dump(mode="json")
            stock = next((x for x in data["stocks"] if x.entity_id == item.entity_id), None)
            if stock:
                payload["stock"] = stock.model_dump(mode="json")
            insert_once(
                "rie_entities",
                {
                    "id": item.entity_id,
                    "entity_type": item.entity_type,
                    "display_name": item.display_name,
                    "metadata": payload,
                    "created_at": now,
                },
            )
        for stock_seed in data["stocks"]:
            insert_once(
                "rie_entity_aliases",
                {
                    "id": identifier("alias:" + stock_seed.ticker),
                    "entity_id": stock_seed.entity_id,
                    "symbol": stock_seed.ticker,
                    "exchange": stock_seed.exchange,
                    "effective_from": date(2025, 2, 24) if stock_seed.ticker == "SNDK" else None,
                    "external_id": None,
                },
            )
        for narrative_seed in data["narratives"]:
            insert_once(
                "rie_narratives",
                {
                    "id": narrative_seed.narrative_id,
                    "ticker_entity_id": f"CO_{narrative_seed.primary_ticker}",
                    "is_template": True,
                    "status": narrative_seed.status,
                    "created_at": now,
                },
            )
            version_id = identifier(
                f"narrative:{narrative_seed.narrative_id}:{narrative_seed.version}"
            )
            table = metadata.tables["rie_narrative_versions"]
            old = conn.execute(
                select(table.c.config).where(table.c.id == version_id)
            ).scalar_one_or_none()
            payload = narrative_seed.model_dump(mode="json")
            if old is not None and old != payload:
                raise ValueError("Cannot overwrite an immutable narrative version")
            insert_once(
                "rie_narrative_versions",
                {
                    "id": version_id,
                    "narrative_id": narrative_seed.narrative_id,
                    "version_number": narrative_seed.version,
                    "title": narrative_seed.title,
                    "thesis": narrative_seed.thesis,
                    "horizon_months": narrative_seed.horizon_months,
                    "config": payload,
                    "published_at": now,
                    "available_at": now,
                },
            )
            for rank, driver in enumerate(narrative_seed.driver_ids, 1):
                insert_once(
                    "rie_narrative_drivers",
                    {
                        "narrative_version_id": version_id,
                        "driver_entity_id": driver,
                        "priority": rank,
                    },
                )
        for edge_seed in data["relationships"]:
            insert_once(
                "rie_relationships",
                {
                    "id": edge_seed.relation_id,
                    "from_entity_id": edge_seed.from_entity,
                    "to_entity_id": edge_seed.to_entity,
                    "relation_family": edge_seed.family,
                    "mechanism": edge_seed.mechanism,
                    "sign": edge_seed.sign,
                    "lag": edge_seed.lag,
                    "strength": None,
                    "confidence": 0,
                    "status": "candidate",
                    "recorded_at": edge_seed.recorded_at,
                    "valid_from": edge_seed.valid_from,
                    "valid_until": edge_seed.valid_until,
                    "metadata": edge_seed.model_dump(mode="json"),
                },
            )
        count = conn.execute(select(entities.c.id).where(entities.c.entity_type == "company")).all()
        if len(count) != 5:
            raise ValueError("Database contains non-pilot companies; import rolled back")
    digest = hashlib.sha256(
        json.dumps(
            {
                k: [x.model_dump(mode="json") for x in v]
                for k, v in (
                    ("entities", data["entities"]),
                    ("stocks", data["stocks"]),
                    ("narratives", data["narratives"]),
                    ("relationships", data["relationships"]),
                )
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "stocks": 5,
        "entities": len(data["entities"]),
        "narratives": 10,
        "candidate_relationships": 40,
        "seed_sha256": digest,
        "identity_status": "pending_SEC_verification",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config"))
    args = parser.parse_args()
    print(json.dumps(seed(database(), args.config), indent=2))


if __name__ == "__main__":
    main()
