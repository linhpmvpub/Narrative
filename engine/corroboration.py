"""Versioned cross-source research; independent publisher is not causal identification."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v10 import corroborations


def ingest(engine, payload, captures):
    now = datetime.now(UTC)
    sources = {s["id"]: s for s in payload["sources"]}
    if len(sources) != len(payload["sources"]) or not sources:
        raise ValueError("Unique source identifiers required")
    for s in sources.values():
        if (
            urlparse(s["url"]).scheme != "https"
            or not s["publisher"]
            or len(s["capture_sha256"]) != 64
        ):
            raise ValueError("Source provenance required")
        if (
            not re.fullmatch(r"[a-z0-9-]+", s["id"])
            or hashlib.sha256(captures.get(s["id"], b"")).hexdigest() != s["capture_sha256"]
        ):
            raise ValueError("Source capture hash mismatch")
        captured = datetime.fromisoformat(s["retrieved_at"])
        published = datetime.fromisoformat(s["published_at"])
        if captured.tzinfo is None or published.tzinfo is None or not published <= captured <= now:
            raise ValueError("Invalid source time")
        if len(s.get("quote", "").split()) > 25:
            raise ValueError("Keep excerpts brief")
    for a in payload["assessments"]:
        if (
            not a["source_ids"]
            or not set(a["source_ids"]) <= sources.keys()
            or not a["limitations"]
        ):
            raise ValueError("Source references and causal limitations required")
        if a["graph_eligible"] is not False or a["causal_effect_identified"] is not False:
            raise ValueError("Research cannot silently grant graph approval")
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        conn.execute(select(database_mode).with_for_update()).one()
        previous = (
            conn.execute(select(corroborations).order_by(corroborations.c.version.desc()).limit(1))
            .mappings()
            .first()
        )
        if previous and previous["payload"] == payload:
            return {"status": "duplicate", "id": previous["id"]}
        version = previous["version"] + 1 if previous else 1
        key = digest([version, payload])
        conn.execute(
            corroborations.insert().values(
                id=key, version=version, available_at=now, payload=payload
            )
        )
    return {
        "status": "created",
        "id": key,
        "sources": len(sources),
        "assessments": len(payload["assessments"]),
    }


def at(conn, cutoff):
    row = (
        conn.execute(
            select(corroborations)
            .where(corroborations.c.available_at <= cutoff)
            .order_by(corroborations.c.version.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not row:
        return {}
    sources = {s["id"]: s for s in row["payload"]["sources"]}
    return {
        a["relation_id"]: {
            **a,
            "sources": [sources[i] for i in a["source_ids"]],
            "assessment_version": row["version"],
            "available_at": utc(row["available_at"]).isoformat(),
            "review_origin": "AI_SOURCE_ASSESSMENT_NOT_HUMAN_LABEL",
        }
        for a in row["payload"]["assessments"]
    }


def main():
    import argparse

    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True)
    args = parser.parse_args()
    engine = database()
    try:
        payload = json.loads(args.file.read_text(encoding="utf-8"))
        captures = {}
        for source in payload["sources"]:
            if not re.fullmatch(r"[a-z0-9-]+", source["id"]):
                raise ValueError("Invalid source ID")
            extension = ".pdf" if "pdf" in source["content_type"] else ".html"
            captures[source["id"]] = (args.captures / (source["id"] + extension)).read_bytes()
        print(json.dumps(ingest(engine, payload, captures)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
