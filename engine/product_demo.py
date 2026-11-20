"""Generate a private synthetic P4 feed using an explicitly initialized demo database."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from engine.adapters.fixture import FixtureSourceAdapter
from engine.api.accounts import Principal, provision
from engine.api.product import SubscriptionBody, subscribe
from engine.db import database
from engine.graph.demo import install_context
from engine.models.schema_v4 import users
from engine.replay import replay
from engine.storybook.product import project, timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    engine = database()
    try:
        context = install_context(
            engine,
            root / "config",
            root / "fixtures/demo_verified_relationships.json",
            root / "fixtures/p3_demo_policy.json",
        )
        with engine.connect() as conn:
            uid = conn.execute(
                select(users.c.id).where(users.c.tenant_id == "local-p4-demo")
            ).scalar_one_or_none()
        if uid is None:
            uid, _ = provision(engine, "local-p4-demo")
        user = Principal(uid, "local-p4-demo", "member")
        sid = subscribe(
            SubscriptionBody(thread_kind="narrative", target_id="N08", confirmed=True),
            user,
            "demo-N08",
        )["id"]
        subscribe(
            SubscriptionBody(thread_kind="stock", target_id="CO_DELL", confirmed=True),
            user,
            "demo-DELL",
        )
        records = FixtureSourceAdapter().read(root / "fixtures/events.jsonl")
        result = replay(engine, records, as_of, context)
        project(engine, records, result)
        with engine.connect() as conn:
            feed = timeline(conn, sid, as_of, 100)
        sample = next(i for i in feed["items"] if i["card"]["event_id"] == "F021")
        args.output.write_text(
            json.dumps(
                {
                    "is_synthetic": True,
                    "is_public": False,
                    "delivery": "disabled",
                    "as_of": as_of.isoformat(),
                    "item": sample,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "artifact": str(args.output),
                    "feed_entries": len(feed["items"]),
                    "delivery": "disabled",
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
