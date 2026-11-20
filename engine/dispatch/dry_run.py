from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.engine import Engine

from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v3 import dispatch_plans, dispatch_users
from engine.settings import Settings


class DispatchPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    timezone: str = "UTC"
    quiet_start_hour: int | None = Field(default=None, ge=0, le=23)
    quiet_end_hour: int | None = Field(default=None, ge=0, le=23)
    daily_cap: int = Field(default=5, ge=0)
    minimum_interval_seconds: int = Field(default=300, ge=0)
    kill_switch: bool = True


def plan_dry_run(
    engine: Engine,
    user_id: str,
    candidates: list[dict],
    at: datetime,
    preferences: DispatchPreferences,
) -> list[dict]:
    Settings.from_env()  # Attempts to enable delivery are rejected even here.
    if not user_id.strip() or at.tzinfo is None:
        raise ValueError("User and aware timestamp required")
    zone = ZoneInfo(preferences.timezone)
    local = at.astimezone(zone)
    start, end = preferences.quiet_start_hour, preferences.quiet_end_hour
    if (start is None) != (end is None):
        raise ValueError("Quiet hours require both boundaries")
    quiet = False
    if start is not None and end is not None:
        quiet = (
            start <= local.hour < end if start < end else local.hour >= start or local.hour < end
        )
    grouped: dict[tuple, list[dict]] = {}
    for candidate in candidates:
        trace = candidate["trace"]
        if trace["decision"] not in ("push", "digest") or not trace["event_version_id"]:
            continue
        required = [
            "source_rights",
            "synthetic_isolation",
            "narrative_mode",
            "provenance",
            "available_as_of",
            "identity",
            "novelty",
            "comparison_basis",
            "core_numbers_consistent",
            "contract_claim_evidenced",
            "quality_digest",
            "verified_path",
        ]
        if trace["decision"] == "push":
            required += ["quality_push", "materiality_known", "direction_and_conditions"]
        if any(not trace["gate_results"].get(key, False) for key in required):
            raise ValueError("Cannot plan a decision that failed its gates")
        if datetime.fromisoformat(trace["as_of"]) > at:
            raise ValueError("Cannot dispatch a future decision")
        grouped.setdefault((trace["canonical_event_key"], trace["event_version_id"]), []).append(
            candidate
        )
    results = []
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            conn.exec_driver_sql("BEGIN IMMEDIATE")
        elif engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert
        else:
            raise ValueError("Unsupported transactional backend")
        statement = (
            sqlite_insert(dispatch_users)
            if engine.dialect.name == "sqlite"
            else pg_insert(dispatch_users)
        )
        conn.execute(statement.values(user_id=user_id).on_conflict_do_nothing())
        conn.execute(
            select(dispatch_users).where(dispatch_users.c.user_id == user_id).with_for_update()
        ).one()
        history = (
            conn.execute(
                select(dispatch_plans).where(
                    dispatch_plans.c.user_id == user_id, dispatch_plans.c.planned_at <= at
                )
            )
            .mappings()
            .all()
        )
        reserved = [row for row in history if row["result"]["recommendation"] == "push"]
        day_count = sum(
            utc(row["planned_at"]).astimezone(zone).date() == local.date() for row in reserved
        )
        last_push = max((utc(row["planned_at"]) for row in reserved), default=None)
        groups = sorted(
            grouped.items(), key=lambda entry: -max(c["trace"]["score"] or 0 for c in entry[1])
        )
        for (canonical, version), group in groups:
            key = digest([user_id, canonical, version])
            existing = conn.execute(
                select(dispatch_plans.c.result).where(dispatch_plans.c.id == key)
            ).scalar_one_or_none()
            if existing is not None:
                results.append({**existing, "idempotent_retry": True})
                continue
            ordered = sorted(group, key=lambda c: (-(c["trace"]["score"] or 0), c["thread_id"]))
            primary = ordered[0]["trace"]
            recommendation, reason = primary["decision"], "eligible_dry_run"
            if preferences.kill_switch:
                recommendation, reason = "suppressed", "kill_switch"
            elif any(c["trace"]["is_synthetic"] for c in group):
                recommendation, reason = "suppressed", "synthetic_never_delivered"
            elif recommendation == "push" and quiet:
                recommendation, reason = "digest", "quiet_hours"
            elif recommendation == "push" and day_count >= preferences.daily_cap:
                recommendation, reason = "digest", "daily_cap"
            elif (
                recommendation == "push"
                and last_push is not None
                and (at - last_push).total_seconds() < preferences.minimum_interval_seconds
            ):
                recommendation, reason = "digest", "minimum_interval"
            result = {
                "plan_id": key,
                "user_id": user_id,
                "canonical_event_key": canonical,
                "event_version_id": version,
                "related_thread_ids": sorted({c["thread_id"] for c in group}),
                "primary_narrative_id": primary["narrative_id"],
                "also_relevant_to": sorted(
                    {c["trace"]["narrative_id"] for c in group} - {primary["narrative_id"]}
                ),
                "recommendation": recommendation,
                "reason": reason,
                "delivery_status": "dry_run",
                "sent_at": None,
                "provider_message_id": None,
                "preferences": preferences.model_dump(),
            }
            conn.execute(
                dispatch_plans.insert().values(
                    id=key,
                    user_id=user_id,
                    canonical_key=canonical,
                    event_version_id=version,
                    planned_at=at,
                    result=result,
                    delivery_status="dry_run",
                    sent_at=None,
                )
            )
            results.append(result)
            if recommendation == "push":
                day_count += 1
                last_push = at
    return results
