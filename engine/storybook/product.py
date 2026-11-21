"""Immutable private projections of trusted synthetic evaluations."""

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, Query
from sqlalchemy import and_, or_, select

from engine.api.accounts import hashed, transaction
from engine.api.product import User, narratives, owned, router, subs, versions
from engine.db import database
from engine.dispatch.dry_run import DispatchPreferences, plan_dry_run
from engine.graph.demo import load_context
from engine.graph.matcher import Edge
from engine.graph.review import check_evidence
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v4 import card_threads, cards, feedback, metadata, shares, users
from engine.replay import event_input
from engine.scoring.policy import NarrativeInput, evaluate, render_card
from engine.settings import Settings


def custom_outputs(conn, records, context, as_of, subscription):
    nid = subscription["narrative_id"]
    narrative = conn.execute(select(narratives).where(narratives.c.id == nid)).mappings().one()
    if narrative["is_template"]:
        return []
    version = (
        conn.execute(
            select(versions)
            .where(versions.c.narrative_id == nid, versions.c.available_at <= as_of)
            .order_by(versions.c.version_number.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not version or not version["approved_by"]:
        return []
    config = version["config"]
    ni = NarrativeInput(
        id=nid,
        version_id=version["id"],
        ticker=config["primary_ticker"],
        available_at=utc(version["available_at"]),
        outcomes=config["outcomes"],
        hypothesis_polarity=config["hypothesis_polarity"],
        watch_next=config["disconfirmation"],
        is_synthetic=True,
    )
    receipts = metadata.tables["rie_ingestion_receipts"]
    lookup = {
        r["input_id"]: r
        for r in conn.execute(select(receipts).where(receipts.c.as_of == as_of)).mappings()
    }
    edges = [Edge.model_validate(e) for e in context["edges"]]
    outputs = []
    for record in records:
        event = event_input(record, lookup[record.event_id], context)
        # Compiler scope is enforced before matching, not merely displayed in the UI.
        allowed = set(config["driver_ids"]) | set(config["outcomes"])
        event = event.model_copy(
            update={
                "observations": tuple(obs for obs in event.observations if obs.metric_id in allowed)
            }
        )
        trace = evaluate(
            event, ni, edges, set(context["nodes"]), as_of, demo=True, max_hops=config["max_hops"]
        )
        trace["compiled_scope"] = config
        trace["decision_id"] = digest([trace, version["id"]])
        outputs.append(
            {"is_synthetic": True, "decision_trace": trace, "card": render_card(event, ni, trace)}
        )
    return outputs


def project(engine, records, replay_result):
    as_of = datetime.fromisoformat(replay_result["as_of"])
    with engine.connect() as conn:
        context = load_context(conn, replay_result["context_id"], as_of)
        user_ids = list(conn.execute(select(users.c.id)).scalars())
    count = 0
    event_versions = metadata.tables["rie_event_versions"]
    for user_id in user_ids:
        candidates = []
        with transaction(engine, user_id) as conn:
            subscriptions = list(
                conn.execute(
                    select(subs).where(subs.c.user_id == user_id, subs.c.disabled_at.is_(None))
                ).mappings()
            )
            for subscription in subscriptions:
                outputs = (
                    replay_result["results"]
                    + custom_outputs(conn, records, context, as_of, subscription)
                    if subscription["narrative_id"]
                    else replay_result["results"]
                )
                # Process original versions before corrections; tie-break deterministically.
                outputs = sorted(
                    outputs,
                    key=lambda x: (x["card"]["source_available_at"], x["card"]["narrative_id"]),
                )
                for output in outputs:
                    trace, card = output["decision_trace"], output["card"]
                    if subscription["thread_kind"] == "narrative":
                        if trace["narrative_id"] != subscription["narrative_id"]:
                            continue
                    elif "CO_" + card["primary_ticker"] != subscription["stock_entity_id"]:
                        continue
                    vid = trace["event_version_id"]
                    if not vid or trace["decision"] == "suppressed":
                        continue
                    version = (
                        conn.execute(select(event_versions).where(event_versions.c.id == vid))
                        .mappings()
                        .one()
                    )
                    if utc(version["available_at"]) > as_of:
                        continue
                    previous = conn.execute(
                        select(cards.c.id).where(
                            cards.c.user_id == user_id,
                            cards.c.event_version_id == version["supersedes_version_id"],
                        )
                    ).scalar_one_or_none()
                    prior_link = (
                        previous
                        and conn.execute(
                            select(card_threads.c.card_id).where(
                                card_threads.c.card_id == previous,
                                card_threads.c.thread_id == subscription["id"],
                            )
                        ).first()
                    )
                    if (
                        not trace["selected_path"]
                        and trace["decision"] != "storybook"
                        and not prior_link
                    ):
                        continue
                    cid = digest([user_id, trace["canonical_event_key"], vid])
                    candidates.append({"thread_id": subscription["id"], "trace": trace})
                    if conn.execute(
                        select(card_threads.c.card_id).where(
                            card_threads.c.card_id == cid,
                            card_threads.c.thread_id == subscription["id"],
                        )
                    ).first():
                        continue
                    if not conn.execute(select(cards.c.id).where(cards.c.id == cid)).first():
                        conn.execute(
                            cards.insert().values(
                                id=cid,
                                user_id=user_id,
                                canonical_key=trace["canonical_event_key"],
                                event_version_id=vid,
                                correction_of=previous,
                            )
                        )
                    conn.execute(
                        card_threads.insert().values(
                            card_id=cid,
                            thread_id=subscription["id"],
                            available_at=as_of,
                            source_at=utc(version["available_at"]),
                            recorded_at=datetime.now(UTC),
                            snapshot=output,
                        )
                    )
                    count += 1
        # Gather all owned active threads before bundling; no transport is installed.
        plan_dry_run(engine, user_id, candidates, as_of, DispatchPreferences())
    return count


def timeline(conn, sid, as_of, limit, cursor=None, *, public=False):
    recorded = datetime.now(UTC)
    last = None
    if cursor:
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor))
            if decoded["thread"] != sid or decoded["as_of"] != as_of.isoformat():
                raise ValueError()
            recorded = datetime.fromisoformat(decoded["recorded"])
            last = (datetime.fromisoformat(decoded["last"][0]), decoded["last"][1])
            if recorded.tzinfo is None or last[0].tzinfo is None or recorded > datetime.now(UTC):
                raise ValueError()
        except (ValueError, TypeError, KeyError, IndexError):
            raise HTTPException(422, "Invalid cursor") from None
    query = (
        select(card_threads, cards.c.correction_of)
        .join(cards)
        .where(
            card_threads.c.thread_id == sid,
            card_threads.c.available_at <= as_of,
            card_threads.c.recorded_at <= recorded,
        )
    )
    # Exclude development notices before pagination, including pre-existing public shares.
    if public or not Settings.from_env().dev_informational_feed:
        ev = metadata.tables["rie_event_versions"]
        event = metadata.tables["rie_events"]
        dev_versions = (
            select(ev.c.id).join(event).where(event.c.event_type == "development_sec_notice")
        )
        query = query.where(cards.c.event_version_id.not_in(dev_versions))
    if last:
        query = query.where(
            or_(
                card_threads.c.source_at > last[0],
                and_(card_threads.c.source_at == last[0], card_threads.c.card_id > last[1]),
            )
        )
    rows = list(
        conn.execute(
            query.order_by(card_threads.c.source_at, card_threads.c.card_id).limit(limit + 1)
        ).mappings()
    )
    items = []
    for row in rows[:limit]:
        related = list(
            conn.execute(
                select(card_threads.c.thread_id).where(
                    card_threads.c.card_id == row["card_id"],
                    card_threads.c.available_at <= as_of,
                    card_threads.c.recorded_at <= recorded,
                )
            ).scalars()
        )
        label = conn.execute(
            select(feedback.c.label).where(
                feedback.c.card_id == row["card_id"], feedback.c.active.is_(True)
            )
        ).scalar_one_or_none()
        lifecycle = {}
        if row["snapshot"]["card"].get("private_only"):
            ev = metadata.tables["rie_event_versions"]
            current_event = (
                select(ev.c.event_id)
                .where(
                    ev.c.id
                    == select(cards.c.event_version_id)
                    .where(cards.c.id == row["card_id"])
                    .scalar_subquery()
                )
                .scalar_subquery()
            )
            latest = (
                conn.execute(
                    select(ev)
                    .where(
                        ev.c.event_id == current_event,
                        ev.c.available_at <= as_of,
                        ev.c.available_at <= recorded,
                    )
                    .order_by(ev.c.version_number.desc())
                    .limit(1)
                )
                .mappings()
                .one()
            )
            status = latest["normalized_claim"].get("source_status", "active")
            lifecycle = {
                "effective_source_status": status,
                "latest_event_version_id": latest["id"],
                "is_superseded": latest["id"]
                != row["snapshot"]["decision_trace"]["event_version_id"],
                "impact_eligible": False,
            }
        items.append(
            {
                "id": row["card_id"],
                **row["snapshot"],
                **lifecycle,
                "available_at": utc(row["available_at"]).isoformat(),
                "correction_of": row["correction_of"],
                "related_thread_ids": sorted(related),
                "state_delta": "correction"
                if row["correction_of"]
                else row["snapshot"]["decision_trace"]["stance"].lower(),
                "personal_relevance": "lower"
                if label == "NOT_RELEVANT"
                else "higher"
                if label == "USEFUL"
                else "default",
            }
        )
    next_cursor = None
    if len(rows) > limit:
        lastrow = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "thread": sid,
                    "as_of": as_of.isoformat(),
                    "recorded": recorded.isoformat(),
                    "last": [utc(lastrow["source_at"]).isoformat(), lastrow["card_id"]],
                }
            ).encode()
        ).decode()
    return {
        "items": items,
        "next_cursor": next_cursor,
        "as_of": as_of.isoformat(),
        "is_public": False,
        "delivery": "disabled",
    }


def observations(conn, subscription, as_of):
    entity_id = subscription["stock_entity_id"]
    if entity_id is None:
        entity_id = conn.execute(
            select(narratives.c.ticker_entity_id).where(
                narratives.c.id == subscription["narrative_id"]
            )
        ).scalar_one()
    m, e, d, s = (
        metadata.tables[n]
        for n in ("rie_metric_observations", "rie_evidence", "rie_documents", "rie_sources")
    )
    rows = conn.execute(
        select(m, e.c.url)
        .select_from(m.join(e).join(d).join(s))
        .where(
            m.c.entity_id == entity_id,
            m.c.first_available_at <= as_of,
            e.c.created_at <= as_of,
            e.c.verified_at <= as_of,
            d.c.published_at <= as_of,
            d.c.first_seen_at <= as_of,
            d.c.available_at <= as_of,
            d.c.retrieved_at <= as_of,
            s.c.rights_status == "approved",
            s.c.created_at <= as_of,
            d.c.is_synthetic.is_(False),
        )
        .order_by(m.c.first_available_at, m.c.id)
    ).mappings()
    observations = []
    for row in rows:
        try:
            check_evidence(conn, [row["evidence_id"]], as_of)
        except ValueError:
            # An approved source alone does not establish a reviewed citation/span.
            continue
        observations.append(dict(row))
    return observations


@router.post("/development-feed/refresh")
def refresh_development_feed(user: User):
    """Owner-scoped, idempotent local projection. Never initiates network collection."""
    if not Settings.from_env().dev_informational_feed:
        return {"enabled": False, "new_private_links": 0, "delivery": "disabled"}
    from engine.development_feed import project as project_development

    engine = database()
    try:
        return {
            "enabled": True,
            "new_private_links": project_development(engine, user.id),
            "delivery": "disabled",
        }
    finally:
        engine.dispose()


@router.get("/threads/{thread_id}/feed")
@router.get("/threads/{thread_id}/story")
def story(
    thread_id: UUID,
    user: User,
    as_of: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
):
    cutoff = as_of or datetime.now(UTC)
    if cutoff.tzinfo is None:
        raise HTTPException(422, "Timezone-aware as_of required")
    engine = database()
    try:
        with engine.connect() as conn:
            subscription = owned(conn, subs, str(thread_id), user)
            result = timeline(conn, str(thread_id), cutoff, limit, cursor)
            result["financial_observations"] = observations(conn, subscription, cutoff)
            result["financial_series"] = "discrete_reported_observations_only"
            result["price_series"] = "unavailable"
            return result
    finally:
        engine.dispose()


@router.get("/public/stories/{token}")
def public_story(token: str, limit: int = Query(default=50, ge=1, le=100)):
    engine = database()
    try:
        with engine.connect() as conn:
            share = (
                conn.execute(
                    select(shares).where(
                        shares.c.token_hash == hashed(token), shares.c.active.is_(True)
                    )
                )
                .mappings()
                .first()
            )
            if not share:
                raise HTTPException(404, "Story not found")
            private = timeline(conn, share["thread_id"], datetime.now(UTC), limit, public=True)
            # Allowlist excludes user-authored hypotheses, monitoring conditions and feedback.
            allowed = (
                "is_synthetic",
                "headline",
                "what_changed",
                "evidence_urls",
                "source_published_at",
                "source_available_at",
                "delivery_status",
            )
            return {
                "is_public": True,
                "items": [
                    {
                        **{k: item["card"][k] for k in allowed},
                        "is_correction": bool(item["correction_of"]),
                    }
                    for item in private["items"]
                ],
            }
    finally:
        engine.dispose()
