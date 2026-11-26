"""Offline regressions for the common decision projection and current RSS bridge."""

import json
from datetime import UTC, datetime

from sqlalchemy import update
from test_company_profiles import dossier as dossier
from test_profile_news import linked as linked

from engine.company_profiles import available_bundles
from engine.core_decisions import POLICY, feed, project
from engine.ingestion.contracts import digest
from engine.models.schema_v13 import news_sources
from engine.profile_news import candidate_feed


def test_real_pipeline_revision_withdrawal_and_pin(db, linked):
    root, _, insert, config, _ = linked
    bundles = available_bundles()["items"]
    data = {
        "profiles": [{"id": b.id, "sha256": digest(b.model_dump(mode="json"))} for b in bundles]
    }
    with db.begin() as conn:
        conn.execute(update(news_sources).values(last_success=datetime.now(UTC)))
    with db.connect() as conn:
        result = feed(conn, data, root.parent)
    assert result["items"]
    first = result["items"][0]
    assert first["financial_magnitude"] == first["direction"] == first["horizon"] == "UNKNOWN"
    assert first["priority"] == "SECTOR_CHANGE_CONTEXT"
    insert(title="Server memory prices fall")
    with db.connect() as conn:
        second = feed(conn, data, root.parent)["items"][0]
    assert first["id"] == second["id"]
    assert first["revision_sha256"] != second["revision_sha256"]
    with db.connect() as conn:
        assert not feed(conn, {"profiles": []}, root.parent)["items"]
    insert(title="This article was withdrawn. Server memory prices rise")
    with db.connect() as conn:
        assert not feed(conn, data, root.parent)["items"]


def test_bundling_no_duplicate_narratives_or_truncated_paths(db, linked):
    with db.connect() as conn:
        items = candidate_feed(conn)["items"]
    policy = json.loads(POLICY.read_text())
    assert len(project(items + items, policy)) == len(project(items, policy))
    for item in items:
        for link in item["links"]:
            link["paths_truncated"] = True
    assert not project(items, policy)


def test_stale_poll_cannot_publish_context(db, linked):
    root = linked[0]
    bundles = available_bundles()["items"]
    data = {
        "profiles": [{"id": b.id, "sha256": digest(b.model_dump(mode="json"))} for b in bundles]
    }
    with db.connect() as conn:
        assert not feed(conn, data, root.parent)["items"]
