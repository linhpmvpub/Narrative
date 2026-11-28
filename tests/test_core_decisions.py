"""Offline regressions for the common decision projection and current RSS bridge."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
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


def company_setup(db, linked):
    root, profile, insert, _, _ = linked
    profile["company_discovery"] = [
        {
            "id": "issuer-events",
            "kind": "ISSUER_EVENT",
            "names": ["example company"],
            "scope": "Synthetic issuer financial statements only",
            "reviewed_at": profile["available_at"],
            "review_until": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
            "evidence": profile["relationships"][0]["evidence"],
        }
    ]
    seal(root, profile)
    insert(title="Example company reports financial results", summary="Quarterly release.")
    with db.begin() as conn:
        conn.execute(update(news_sources).values(last_success=datetime.now(UTC)))
    bundles = available_bundles()["items"]
    pinned = {
        "profiles": [{"id": b.id, "sha256": digest(b.model_dump(mode="json"))} for b in bundles]
    }
    return root, profile, pinned


def test_company_context_revision_and_narrative_dedup(db, linked):
    root, _, pinned = company_setup(db, linked)

    def result():
        with db.connect() as conn:
            return feed(conn, pinned, root.parent)

    first = result()
    assert not first["items"] and not first["background"]
    card = first["company_context"][0]
    assert card["narratives"] == [] and card["delivery"] == "disabled"
    assert card["direction"] == card["financial_magnitude"] == card["horizon"] == "UNKNOWN"
    linked[2](title="Example company announces financial results", summary="Quarterly update.")
    corrected = result()["company_context"][0]
    assert corrected["id"] == card["id"]
    assert corrected["revision_sha256"] != card["revision_sha256"]
    linked[2](
        title="Example company reports financial results", summary="Server memory prices rise."
    )
    combined = result()
    assert not combined["company_context"]
    assert len(combined["items"] + combined["background"]) == 1
    assert (combined["items"] + combined["background"])[0]["company_discovery"]


@pytest.mark.parametrize("fault", ["withdrawn", "stale", "old", "unarchived", "pin", "disabled"])
def test_company_context_fails_closed(db, linked, fault):
    root, profile, pinned = company_setup(db, linked)
    if fault == "withdrawn":
        linked[2](title="This article was withdrawn. Example company reports financial results")
    elif fault == "stale":
        with db.begin() as conn:
            conn.execute(
                update(news_sources).values(last_success=datetime.now(UTC) - timedelta(days=1))
            )
    elif fault == "old":
        linked[2](title="Example company reports financial results", age=31)
    elif fault == "unarchived":
        linked[2](
            title="Example company reports financial results",
            summary="New revision.",
            archive=False,
        )
    elif fault == "pin":
        pinned = {"profiles": []}
    else:
        profile["company_discovery"][0]["enabled"] = False
        seal(root, profile)
        bundles = available_bundles()["items"]
        pinned = {
            "profiles": [{"id": b.id, "sha256": digest(b.model_dump(mode="json"))} for b in bundles]
        }
    with db.connect() as conn:
        assert not feed(conn, pinned, root.parent)["company_context"]
