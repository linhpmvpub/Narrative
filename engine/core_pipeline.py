"""Run the bounded local RSS → current profiles → context card pipeline."""

import argparse
import json
from collections import Counter
from pathlib import Path

from engine.adapters.news import NewsClient
from engine.core_workspace import build
from engine.db import database
from engine.ingestion.contracts import digest
from engine.news import poll, register
from engine.settings import Settings


def audit(result):
    profiles = []
    for p in result["core"]["profiles"]:
        profiles.append(
            {
                "profile_id": p["profile_id"],
                "ticker": p["ticker"],
                "groups": {
                    name: {
                        "statuses": dict(Counter(c["status"] for c in g["components"])),
                        "unknown": [c["key"] for c in g["components"] if c["status"] == "UNKNOWN"],
                    }
                    for name, g in p["groups"].items()
                },
                "sourced_input_paths": len(p["input_exposure_ids"]),
                "narratives": len(p["narrative_ids"]),
            }
        )
    context = result.get("context", {})
    return {
        "schema": "CORE_PIPELINE_AUDIT_V1",
        "profiles": profiles,
        "context_cards": len(context.get("items", [])),
        "cards_by_ticker": dict(Counter(c["ticker"] for c in context.get("items", []))),
        "price_alerts": len(result["cards"]),
        "scan_truncated": context.get("truncated", False),
        "result_sha256": digest(result),
        "delivery": "disabled",
        "accuracy_evaluated": False,
        "acceptance": "DEVELOPMENT_NOT_RELEASE",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--poll", action="store_true")
    parser.add_argument("--price-board", action="store_true")
    parser.add_argument("--sources", type=Path, default=Path("config/news-sources.json"))
    args = parser.parse_args()
    Settings.from_env()
    if not args.database.startswith("sqlite:///"):
        parser.error("This local pipeline requires an explicit SQLite database")
    if args.output.exists():
        parser.error("Use a new output directory to preserve previous results")
    db = database(args.database)
    try:
        collection = []
        if args.poll:
            configs = json.loads(args.sources.read_text(encoding="utf-8"))
            register(db, [{**c, "enabled": False} if c["kind"] != "rss" else c for c in configs])
            client = NewsClient(capture_dir=Path("source-cache/rss-captures"))
            try:
                collection = poll(db, client)
            finally:
                client.close()
        with db.connect() as conn:
            result = build(args.manifest, news_conn=conn)
        price = None
        if args.price_board:
            import httpx

            from engine.price_board import URL, ingest

            response = httpx.get(URL, timeout=40, follow_redirects=True)
            response.raise_for_status()
            price = ingest(response.content, args.output.parent / "prices")
        report = audit(result)
        report["price_observation_status"] = price["status"] if price else "NOT_REQUESTED"
        args.output.mkdir(parents=True, exist_ok=False)
        for name, value in [("result", result), ("audit", report), ("collection", collection)]:
            (args.output / (name + ".json")).write_text(
                json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(
            json.dumps(
                {
                    "context_cards": report["context_cards"],
                    "price_alerts": report["price_alerts"],
                    "scan_truncated": report["scan_truncated"],
                    "delivery": "disabled",
                }
            )
        )
    finally:
        db.dispose()


if __name__ == "__main__":
    main()
