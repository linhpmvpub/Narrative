from datetime import timedelta

import pytest
from sqlalchemy import func, select
from test_policy import NOW, decide, event, narrative

from engine.dispatch.dry_run import DispatchPreferences, plan_dry_run
from engine.models.schema_v3 import dispatch_plans


def candidates(key="test-key", version="v1"):
    trace = decide(event(canonical_key=key, event_version_id=version))
    return [
        {"thread_id": "stock:MU", "trace": trace},
        {"thread_id": "narrative:N01", "trace": trace},
    ]


def test_bundle_retry_and_user_isolation(db):
    prefs = DispatchPreferences(kill_switch=False)
    result = plan_dry_run(db, "A", candidates(), NOW, prefs)
    assert len(result) == 1 and len(result[0]["related_thread_ids"]) == 2
    assert result[0]["recommendation"] == "push"
    assert result[0]["delivery_status"] == "dry_run" and result[0]["sent_at"] is None
    assert plan_dry_run(db, "A", candidates(), NOW, prefs)[0]["idempotent_retry"]
    assert plan_dry_run(db, "B", candidates(), NOW, prefs)[0]["user_id"] == "B"
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(dispatch_plans)) == 2


@pytest.mark.parametrize(
    "prefs,reason",
    [
        (DispatchPreferences(), "kill_switch"),
        (DispatchPreferences(kill_switch=False, daily_cap=0), "daily_cap"),
        (
            DispatchPreferences(
                kill_switch=False, timezone="Asia/Bangkok", quiet_start_hour=22, quiet_end_hour=8
            ),
            "quiet_hours",
        ),
    ],
)
def test_controls(db, prefs, reason):
    result = plan_dry_run(db, "A", candidates(), NOW, prefs)[0]
    assert result["reason"] == reason
    assert result["recommendation"] != "push" and result["sent_at"] is None


def test_daily_cap_and_interval(db):
    prefs = DispatchPreferences(kill_switch=False, daily_cap=1, minimum_interval_seconds=0)
    assert plan_dry_run(db, "A", candidates(), NOW, prefs)[0]["recommendation"] == "push"
    assert (
        plan_dry_run(db, "A", candidates("second"), NOW + timedelta(seconds=1), prefs)[0]["reason"]
        == "daily_cap"
    )
    prefs = DispatchPreferences(kill_switch=False, minimum_interval_seconds=300)
    plan_dry_run(db, "B", candidates(), NOW, prefs)
    assert (
        plan_dry_run(db, "B", candidates("second"), NOW + timedelta(seconds=1), prefs)[0]["reason"]
        == "minimum_interval"
    )


def test_synthetic_never_sent_and_correction_separate(db):
    trace = decide(
        event(is_synthetic=True, rights="approved_fixture_only"),
        narrative(is_synthetic=True),
        demo=True,
    )
    assert trace["decision"] == "push" and not trace["send_recommendation"]
    result = plan_dry_run(
        db,
        "A",
        [{"thread_id": "test", "trace": trace}],
        NOW,
        DispatchPreferences(kill_switch=False),
    )[0]
    assert result["reason"] == "synthetic_never_delivered"
    prefs = DispatchPreferences(kill_switch=False, minimum_interval_seconds=0)
    plan_dry_run(db, "B", candidates(version="v1"), NOW, prefs)
    corrected = plan_dry_run(db, "B", candidates(version="v2"), NOW, prefs)
    assert corrected[0]["event_version_id"] == "v2"
    assert corrected[0]["sent_at"] is None


def test_failed_gate_cannot_be_promoted_by_dispatch(db):
    items = candidates()
    items[0]["trace"]["gate_results"]["quality_push"] = False
    with pytest.raises(ValueError, match="failed"):
        plan_dry_run(db, "A", items, NOW, DispatchPreferences(kill_switch=False))


def test_notification_flag_cannot_enable_transport(db, monkeypatch):
    monkeypatch.setenv("SEND_NOTIFICATIONS", "true")
    with pytest.raises(ValueError, match="must remain false"):
        plan_dry_run(db, "A", candidates(), NOW, DispatchPreferences(kill_switch=False))
