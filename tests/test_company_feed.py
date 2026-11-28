"""Primary company feed invariance, provenance and independent editorial tiers."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from test_company_profiles import dossier as dossier
from test_company_profiles import seal
from test_profile_news import linked as linked

from engine.company_assessment import assess
from engine.company_feed import feed
from engine.company_profiles import ProfileBundle, audit_binding_routes, available_bundles
from engine.ingestion.contracts import digest
from engine.models.schema_v13 import news_sources


@pytest.fixture
def company(db, linked):
    root, data, insert, _, _ = linked
    rule = dict(scope="Synthetic company source", reviewed_at=data["available_at"],
                review_until=(datetime.now(UTC) + timedelta(days=10)).isoformat(),
                evidence=data["relationships"][0]["evidence"])
    data["company_discovery"] = [
        dict(rule, id="issuer", kind="ISSUER_EVENT", names=["example company"]),
        dict(rule, id="input", kind="FACTOR_EXPOSURE", binding_id="memory",
             relation_ids=["applies"], membership_ids=["owns"], intents=["SUPPLY"]),
    ]
    seal(root, data)
    with db.begin() as conn:
        conn.execute(update(news_sources).values(last_success=datetime.now(UTC)))
    return root, data, insert


def read(db, company):
    root = company[0]
    pins = {"profiles": [{"id": b.id, "sha256": digest(b.model_dump(mode="json"))}
                         for b in available_bundles(root=root.parent)["items"]]}
    with db.connect() as conn:
        return feed(conn, pins, root.parent)


def test_company_selection_priority_invariant_to_narrative_inventory(db, company):
    root, data, insert = company
    insert(title="Example company reports financial results", summary="Server memory prices rise.")
    original = read(db, company)
    assert len(original["items"]) == 1 and not original["narratives_used"]
    first = original["items"][0]
    assert first["assessment"]["tier"] == "ISSUER_DEVELOPMENT"
    data["narratives"] = []
    data["routing_policies"] = []
    for binding in data["factor_bindings"]:
        binding.update(company_only=True, narrative_ids=[])
    audit_binding_routes(ProfileBundle.model_validate(data))
    seal(root, data)
    without = read(db, company)["items"][0]
    assert without["id"] == first["id"]
    assert without["assessment"] == first["assessment"]
    assert without["narratives"] == first["narratives"] == []
    assert without["company_discovery"] == first["company_discovery"]
    assert without["direction"] == without["horizon"] == without["financial_magnitude"] == "UNKNOWN"


@pytest.mark.parametrize("fault", ["stale", "withdrawn", "disabled", "uncaptured", "pin"])
def test_company_source_lifecycle_withholds_all_sections(db, company, fault):
    root, data, insert = company
    insert(title="Example company reports financial results")
    if fault in {"stale", "disabled"}:
        with db.begin() as conn:
            if fault == "stale":
                conn.execute(update(news_sources).values(last_success=datetime.now(UTC)-timedelta(hours=2)))
            else:
                data["company_discovery"][0]["enabled"] = False
                seal(root, data)
    elif fault == "withdrawn":
        insert(title="This article was withdrawn. Example company reports financial results")
    elif fault == "uncaptured":
        insert(title="Example company announces financial results", archive=False)
    if fault == "pin":
        with db.connect() as conn:
            result = feed(conn, {"profiles": []}, root.parent)
    else:
        result = read(db, company)
    assert not result["items"] and not result["background"]


def test_priority_cannot_be_manufactured_from_unrelated_or_uncertain_text(db, company):
    _, _, insert = company
    insert(title="Example company's credit rating could be cut")
    result = read(db, company)
    assert not result["items"] and len(result["background"]) == 1
    insert(title="Sponsored: Example company reports financial results")
    result = read(db, company)
    assert not result["items"] and result["background"][0]["assessment"]["sponsored"]
    assert not assess({"headline": "Company reports record results", "excerpt": ""}, [])["priority"]


def test_company_feed_has_no_narrative_matching_dependency(db, company, monkeypatch):
    import engine.profile_news as news
    monkeypatch.setattr(news, "paths", lambda *a, **k: pytest.fail("Narrative graph traversal called"))
    result = read(db, company)
    assert result["items"] or result["background"]
