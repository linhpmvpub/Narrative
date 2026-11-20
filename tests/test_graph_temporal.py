from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from test_foundations import add_evidence, approve

from engine.graph.matcher import live_edges_as_of
from engine.graph.review import live_edge_eligible
from engine.models.schema_v1 import metadata


def test_approved_snapshot_before_and_after_later_rejection(db):
    evidence = add_evidence(db)
    before = datetime.now(UTC)
    approve(db, [evidence])
    as_of = datetime.now(UTC) + timedelta(seconds=1)
    future = as_of + timedelta(days=1)
    revisions = metadata.tables["rie_relationship_revisions"]
    edges = metadata.tables["rie_relationships"]
    with db.begin() as conn:
        current = conn.execute(select(revisions)).mappings().one()
        rejected = {**current["after"], "status": "rejected", "recorded_at": future.isoformat()}
        conn.execute(
            revisions.insert().values(
                id=str(uuid4()),
                relationship_id="R026",
                before=current["after"],
                after=rejected,
                reviewer_id="reviewer",
                reason="Unit-test later rejection",
                changed_at=future,
            )
        )
        conn.execute(
            edges.update().where(edges.c.id == "R026").values(status="rejected", recorded_at=future)
        )
    with db.connect() as conn:
        assert live_edges_as_of(conn, before) == []
        snapshot = live_edges_as_of(conn, as_of)
        assert len(snapshot) == 1 and snapshot[0].id == "R026"
        assert snapshot[0].eligible(as_of, False)
        assert snapshot[0].conditions == ("contracted_cost_rises",)
        assert live_edge_eligible(conn, "R026", as_of)
        assert live_edges_as_of(conn, future + timedelta(seconds=1)) == []


def test_mutable_verified_row_without_review_is_not_a_snapshot(db):
    with db.begin() as conn:
        edges = metadata.tables["rie_relationships"]
        conn.execute(
            edges.update()
            .where(edges.c.id == "R026")
            .values(
                status="verified",
                verified_at=datetime.now(UTC),
                verified_by="untrusted-direct-write",
            )
        )
    with db.connect() as conn:
        assert live_edges_as_of(conn, datetime.now(UTC)) == []
