import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from engine.adapters.fixture import FixtureSourceAdapter
from engine.db import database
from engine.ingestion.service import ingest_fixtures, initialize_demo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline synthetic ingestion; no alerts or delivery"
    )
    parser.add_argument("--fixture", type=Path, default=Path("fixtures/events.jsonl"))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--demo", action="store_true", required=True)
    parser.add_argument("--initialize-demo", action="store_true")
    args = parser.parse_args()
    records = FixtureSourceAdapter().read(args.fixture)
    engine = database()
    try:
        if args.initialize_demo:
            initialize_demo(engine)
        results = ingest_fixtures(
            engine, records, datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        )
        print(
            json.dumps(
                {
                    "is_synthetic": True,
                    "as_of": args.as_of,
                    "delivery": "disabled",
                    "counts": dict(Counter(x["status"] for x in results)),
                    "results": results,
                },
                indent=2,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
