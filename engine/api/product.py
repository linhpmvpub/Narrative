"""Private product API. Operator replay is explicit and offline."""

import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from engine.api.accounts import Principal, administrator, hashed, principal, write
from engine.db import database
from engine.models.schema_v4 import cards, feedback, metadata, shares

router = APIRouter(prefix="/api/v0")
User = Annotated[Principal, Depends(principal)]
Admin = Annotated[Principal, Depends(administrator)]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]
subs = metadata.tables["rie_subscriptions"]
narratives = metadata.tables["rie_narratives"]
versions = metadata.tables["rie_narrative_versions"]
entities = metadata.tables["rie_entities"]
queue = metadata.tables["rie_review_queue"]
ROOT = Path(__file__).resolve().parents[2]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NarrativeBody(Body):
    primary_ticker: Literal["MU", "NVDA", "AMD", "DELL", "SNDK"]
    title: str = Field(min_length=1, max_length=160)
    thesis: str = Field(min_length=1, max_length=2000)
    horizon_months: int = Field(ge=1, le=60)
    driver_ids: list[str] = Field(min_length=1, max_length=3)
    supporting_evidence: str = Field(min_length=1, max_length=1000)
    challenging_evidence: str = Field(min_length=1, max_length=1000)
    disconfirmation: str = Field(min_length=1, max_length=1000)
    outcomes: dict[str, Literal[-1, 1]] = Field(min_length=1, max_length=3)
    hypothesis_polarity: Literal["favorable", "adverse"]
    max_hops: Literal[0, 1, 2] = 2


class EditBody(NarrativeBody):
    expected_version: int = Field(ge=1)


class ApprovalBody(Body):
    confirmed: Literal[True]
    expected_version: int = Field(ge=1)


class SubscriptionBody(Body):
    thread_kind: Literal["stock", "narrative"]
    target_id: str = Field(min_length=1, max_length=100)
    confirmed: Literal[True]


class FeedbackBody(Body):
    label: Literal["USEFUL", "ALREADY_KNEW", "NOT_RELEVANT", "UNCLEAR", "WRONG"]
    reason: str = Field(default="", max_length=2000)


class SharingBody(Body):
    is_public: bool


class ReplayBody(Body):
    demo: Literal[True]
    as_of: AwareDatetime


class RelationReview(Body):
    action: Literal["approve", "reject"]
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=20)
    valid_from: AwareDatetime | None = None
    strength: float = Field(default=0, ge=0, le=1)
    confidence: float = Field(default=0, ge=0, le=1)
    routing_basis: str = Field(default="", max_length=2000)
    conditions: list[str] = Field(default_factory=list, max_length=10)


@router.post("/admin/relations/{relation_id}/review")
def review_relation(relation_id: str, body: RelationReview, user: Admin, key: Key = None):
    from decimal import Decimal

    from engine.graph.review import approve_relationship, snapshot

    def action(conn):
        edges = metadata.tables["rie_relationships"]
        before = (
            conn.execute(select(edges).where(edges.c.id == relation_id).with_for_update())
            .mappings()
            .first()
        )
        if not before:
            raise HTTPException(404, "Relationship not found")
        if before["status"] != "candidate":
            raise HTTPException(409, "Review requires a candidate")
        if not body.reason.strip():
            raise HTTPException(422, "Review reason required")
        now = datetime.now(UTC)
        if body.action == "approve":
            try:
                approve_relationship(
                    conn,
                    relation_id,
                    evidence_ids=[str(i) for i in body.evidence_ids],
                    reviewer=user.id,
                    reason=body.reason,
                    reviewed_at=now,
                    valid_from=body.valid_from or now,
                    strength=Decimal(str(body.strength)),
                    confidence=Decimal(str(body.confidence)),
                    routing_basis=body.routing_basis,
                    conditions=tuple(body.conditions),
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
        else:
            values = {"status": "rejected", "recorded_at": now}
            conn.execute(edges.update().where(edges.c.id == relation_id).values(**values))
            revisions = metadata.tables["rie_relationship_revisions"]
            conn.execute(
                revisions.insert().values(
                    id=str(uuid4()),
                    relationship_id=relation_id,
                    before=snapshot(before),
                    after=snapshot({**before, **values}),
                    reviewer_id=user.id,
                    reason=body.reason,
                    changed_at=now,
                )
            )
        return {"id": relation_id, "status": "verified" if body.action == "approve" else "rejected"}

    return write(user, "relation:" + relation_id, key, body.model_dump(mode="json"), action)


def owned(conn, table, item_id, user, field="user_id"):
    row = conn.execute(select(table).where(table.c.id == item_id)).mappings().first()
    # Uniform not-found avoids leaking whether another tenant owns a resource.
    if row is None or row[field] != user.id:
        raise HTTPException(404, "Resource not found")
    return row


def latest(conn, narrative_id):
    return (
        conn.execute(
            select(versions)
            .where(versions.c.narrative_id == narrative_id)
            .order_by(versions.c.version_number.desc())
            .limit(1)
        )
        .mappings()
        .one()
    )


def compile_narrative(conn, body):
    payload = body.model_dump(exclude={"expected_version"})
    drivers = body.driver_ids
    if len(set(drivers)) != len(drivers):
        raise HTTPException(422, "Drivers must be distinct")
    known = dict(conn.execute(select(entities.c.id, entities.c.entity_type)).all())
    if any(d not in known or known[d] == "company" for d in drivers):
        raise HTTPException(422, "Unknown or invalid driver")
    if any(
        known.get(m) != "financial_metric" or not m.startswith(body.primary_ticker + "_")
        for m in body.outcomes
    ):
        raise HTTPException(422, "Outcomes must be registered metrics for the primary company")
    if any(
        not str(payload[k]).strip()
        for k in (
            "title",
            "thesis",
            "supporting_evidence",
            "challenging_evidence",
            "disconfirmation",
        )
    ):
        raise HTTPException(422, "Narrative conditions cannot be blank")
    payload["compiler_version"] = "explicit-scope-v1"
    payload["metrics"] = sorted(body.outcomes)
    return payload


def append_version(conn, nid, config, number, approved_by=None):
    vid = str(uuid4())
    now = datetime.now(UTC)
    conn.execute(
        versions.insert().values(
            id=vid,
            narrative_id=nid,
            version_number=number,
            title=config["title"],
            thesis=config["thesis"],
            horizon_months=config["horizon_months"],
            config=config,
            published_at=now,
            available_at=now,
            approved_by=approved_by,
        )
    )
    drivers = metadata.tables["rie_narrative_drivers"]
    for driver in config["driver_ids"]:
        conn.execute(
            drivers.insert().values(
                narrative_version_id=vid, driver_entity_id=driver, priority=1, config={}
            )
        )
    return {
        "id": nid,
        "version_id": vid,
        "version": number,
        "status": "active" if approved_by else "draft",
        "compiled_scope": config,
        "available_at": now.isoformat(),
        "requires_approval": not bool(approved_by),
    }


@router.post("/narratives")
def create_narrative(body: NarrativeBody, user: User, key: Key = None):
    def action(conn):
        config = compile_narrative(conn, body)
        count = conn.execute(
            select(func.count())
            .select_from(narratives)
            .where(narratives.c.owner_user_id == user.id)
        ).scalar_one()
        if count >= 50:
            raise HTTPException(409, "Draft storage limit reached")
        nid = "custom-" + str(uuid4())
        conn.execute(
            narratives.insert().values(
                id=nid,
                ticker_entity_id="CO_" + body.primary_ticker,
                owner_user_id=user.id,
                is_template=False,
                status="draft",
            )
        )
        return append_version(conn, nid, config, 1)

    return write(user, "create-narrative", key, body.model_dump(), action)


@router.get("/narratives")
def own_narratives(user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            items = []
            for row in conn.execute(
                select(narratives)
                .where(narratives.c.owner_user_id == user.id)
                .order_by(narratives.c.id)
            ).mappings():
                version = latest(conn, row["id"])
                items.append(
                    {
                        "id": row["id"],
                        "status": row["status"],
                        "version": version["version_number"],
                        "title": version["title"],
                        "thesis": version["thesis"],
                        "config": version["config"],
                    }
                )
            return {"items": items}
    finally:
        engine.dispose()


@router.put("/narratives/{narrative_id}")
def edit_narrative(narrative_id: str, body: EditBody, user: User, key: Key = None):
    def action(conn):
        row = owned(conn, narratives, narrative_id, user, "owner_user_id")
        if row["ticker_entity_id"] != "CO_" + body.primary_ticker:
            raise HTTPException(422, "Create a new narrative to change the company")
        old = latest(conn, narrative_id)
        if old["version_number"] != body.expected_version:
            raise HTTPException(409, "Narrative version changed")
        result = append_version(
            conn, narrative_id, compile_narrative(conn, body), body.expected_version + 1
        )
        conn.execute(
            narratives.update().where(narratives.c.id == narrative_id).values(status="draft")
        )
        return result

    return write(user, "edit:" + narrative_id, key, body.model_dump(), action)


@router.post("/narratives/{narrative_id}/approve")
def approve_narrative(narrative_id: str, body: ApprovalBody, user: User, key: Key = None):
    def action(conn):
        row = owned(conn, narratives, narrative_id, user, "owner_user_id")
        old = latest(conn, narrative_id)
        if old["version_number"] != body.expected_version or row["status"] != "draft":
            raise HTTPException(409, "Review the current draft before approval")
        result = append_version(
            conn, narrative_id, old["config"], body.expected_version + 1, user.id
        )
        conn.execute(
            narratives.update().where(narratives.c.id == narrative_id).values(status="active")
        )
        return result

    return write(user, "approve:" + narrative_id, key, body.model_dump(), action)


@router.post("/subscriptions")
def subscribe(body: SubscriptionBody, user: User, key: Key = None):
    def action(conn):
        column = subs.c.stock_entity_id if body.thread_kind == "stock" else subs.c.narrative_id
        if body.thread_kind == "stock":
            valid = conn.execute(
                select(entities.c.id).where(
                    entities.c.id == body.target_id, entities.c.entity_type == "company"
                )
            ).first()
            if not valid:
                raise HTTPException(422, "Unknown stock")
        else:
            row = conn.execute(select(narratives).where(narratives.c.id == body.target_id))
            narrative = row.mappings().first()
            if not narrative or (
                not narrative["is_template"] and narrative["owner_user_id"] != user.id
            ):
                raise HTTPException(404, "Narrative not found")
            if not narrative["is_template"] and narrative["status"] != "active":
                raise HTTPException(409, "Approve the narrative first")
        active = list(
            conn.execute(
                select(subs).where(
                    subs.c.user_id == user.id,
                    subs.c.thread_kind == body.thread_kind,
                    subs.c.disabled_at.is_(None),
                )
            ).mappings()
        )
        for row in active:
            if row[column.name] == body.target_id:
                return {"id": row["id"], "status": "active"}
        if len(active) >= (3 if body.thread_kind == "stock" else 1):
            raise HTTPException(409, "Free-tier subscription limit reached")
        sid = str(uuid4())
        conn.execute(
            subs.insert().values(
                id=sid,
                user_id=user.id,
                thread_kind=body.thread_kind,
                **{column.name: body.target_id},
                preferences={"approved": True},
            )
        )
        return {"id": sid, "status": "active"}

    return write(user, "subscribe", key, body.model_dump(), action)


@router.get("/subscriptions")
def subscriptions(user: User):
    engine = database()
    try:
        with engine.connect() as conn:
            return {
                "items": [
                    dict(r)
                    for r in conn.execute(
                        select(subs).where(subs.c.user_id == user.id, subs.c.disabled_at.is_(None))
                    ).mappings()
                ]
            }
    finally:
        engine.dispose()


@router.delete("/subscriptions/{subscription_id}")
def unsubscribe(subscription_id: UUID, user: User, key: Key = None):
    sid = str(subscription_id)

    def action(conn):
        owned(conn, subs, sid, user)
        conn.execute(
            subs.update()
            .where(subs.c.id == sid, subs.c.disabled_at.is_(None))
            .values(disabled_at=datetime.now(UTC))
        )
        return {"id": sid, "status": "disabled"}

    return write(user, "unsubscribe:" + sid, key, {}, action)


@router.post("/alerts/{card_id}/feedback")
def give_feedback(card_id: str, body: FeedbackBody, user: User, key: Key = None):
    def action(conn):
        owned(conn, cards, card_id, user)
        conn.execute(
            feedback.update()
            .where(
                feedback.c.card_id == card_id,
                feedback.c.user_id == user.id,
                feedback.c.active.is_(True),
            )
            .values(active=False)
        )
        fid = str(uuid4())
        conn.execute(
            feedback.insert().values(
                id=fid,
                card_id=card_id,
                user_id=user.id,
                label=body.label,
                reason=body.reason,
                active=True,
                created_at=datetime.now(UTC),
            )
        )
        if body.label == "WRONG":
            conn.execute(
                queue.insert().values(
                    id=str(uuid4()),
                    item_kind="claim",
                    item_id=card_id,
                    priority=1,
                    reason="User reported WRONG; private feedback " + fid,
                )
            )
        return {
            "id": fid,
            "label": body.label,
            "global_truth_changed": False,
            "used_for": "quality_review" if body.label == "WRONG" else "personal_relevance",
        }

    return write(user, "feedback:" + card_id, key, body.model_dump(), action)


@router.post("/threads/{thread_id}/sharing")
def sharing(thread_id: UUID, body: SharingBody, user: User, key: Key = None):
    sid = str(thread_id)

    def action(conn):
        owned(conn, subs, sid, user)
        conn.execute(shares.update().where(shares.c.thread_id == sid).values(active=False))
        if not body.is_public:
            return {"is_public": False}
        token = secrets.token_urlsafe(32)
        conn.execute(
            shares.insert().values(
                token_hash=hashed(token), thread_id=sid, active=True, created_at=datetime.now(UTC)
            )
        )
        return {"is_public": True, "path": "/api/v0/public/stories/" + token}

    return write(user, "sharing:" + sid, key, body.model_dump(), action)


@router.post("/admin/fixtures/replay")
def replay_fixtures(body: ReplayBody, user: Admin):
    from engine.operations import exclusive_replay

    with exclusive_replay():
        return run_fixture_replay(body, user)


def run_fixture_replay(body: ReplayBody, user: Principal):
    from engine.adapters.fixture import FixtureSourceAdapter
    from engine.graph.demo import install_context
    from engine.replay import replay
    from engine.storybook.product import project

    engine = database()
    try:
        # Caller must initialize an empty, explicitly synthetic database using the CLI.
        context = install_context(
            engine,
            ROOT / "config",
            ROOT / "fixtures/demo_verified_relationships.json",
            ROOT / "fixtures/p3_demo_policy.json",
        )
        records = FixtureSourceAdapter().read(ROOT / "fixtures/events.jsonl")
        result = replay(engine, records, body.as_of, context)
        count = project(engine, records, result)
        return {
            "counts": result["counts"],
            "new_thread_entries": count,
            "is_synthetic": True,
            "delivery": "disabled",
        }
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        engine.dispose()


@router.get("/admin/review-queue")
def review_queue(user: Admin, limit: int = 50):
    engine = database()
    try:
        with engine.connect() as conn:
            return {
                "items": [
                    dict(r)
                    for r in conn.execute(
                        select(queue)
                        .where(queue.c.status == "open")
                        .order_by(queue.c.priority, queue.c.id)
                        .limit(max(1, min(limit, 100)))
                    ).mappings()
                ]
            }
    finally:
        engine.dispose()


@router.get("/admin/eval-report")
def evaluation(user: Admin):
    import json

    path = ROOT / "reports/p3-baselines.json"
    return {
        "historical_evaluation": "pending",
        "synthetic_baseline": json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else None,
    }
