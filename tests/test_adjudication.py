"""Synthetic human votes only: consensus, conflict, provenance and holdout scoring."""

import copy
from datetime import datetime

import pytest
from sqlalchemy import func, select
from test_annotations import assigned as assigned
from test_annotations import base, body, language
from test_development_feed import enabled as enabled
from test_financials_mobile import financial_store as financial_store
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.annotations import import_packet
from engine.evaluation.consensus import freeze, normalized, quality, states
from engine.evaluation.filing_labels import packet
from engine.models.schema_v10 import cases, labels
from engine.models.schema_v11 import adjudications


@pytest.fixture
def frozen(assigned, financial_store, identities):
    pid, rows = assigned
    with financial_store.connect() as conn:
        pack = packet(conn, datetime.fromisoformat(rows[0]["as_of"]))
    freeze(financial_store, pack)
    import_packet(financial_store, rows, [u[0] for u in identities])
    return pid, rows, pack


def submit(client, user, pid, c, **change):
    return client.post(
        base(pid, c["id"]) + "/labels", headers=headers(user), json=body(c, **change)
    )


def state(engine, pid, cid):
    with engine.connect() as conn:
        return next(s for s in states(conn, pid) if s["case"]["id"] == cid)


def decision(s, **changes):
    return {
        "expected_vote_hash": s["vote_hash"],
        "expected_decision_version": s["decision_version"],
        "outcome": "RESOLVED",
        "independent_of_extractor": True,
        "reason": "Synthetic third reviewer checked original source independently",
        "language": "NO_CAUSAL_CLAIM",
        **changes,
    }


def endpoint(pid, cid):
    return f"/api/v0/admin/evaluation/{pid}/cases/{cid}/adjudications"


def test_latest_distinct_votes_and_no_majority(client, identities, frozen, financial_store):
    pid, rows, _ = frozen
    c = language(rows)
    assert submit(client, identities[0], pid, c).status_code == 200
    assert submit(client, identities[0], pid, c, expected_version=1).status_code == 200
    assert state(financial_store, pid, c["id"])["status"] == "WAITING_FOR_TWO_REVIEWERS"
    assert submit(client, identities[1], pid, c).status_code == 200
    assert state(financial_store, pid, c["id"])["status"] == "CONSENSUS"
    with financial_store.connect() as conn:
        report = quality(conn, pid)
    assert report["gold_cases"] == 1
    assert all(m["scored"] == 0 for m in report["holdout"].values())
    assert submit(client, identities[2], pid, c, language="ISSUER_ATTRIBUTION").status_code == 200
    s = state(financial_store, pid, c["id"])
    assert s["status"] == "DISAGREEMENT" and s["gold"] is None and len(s["votes"]) == 3


def test_adjudication_revision_staleness_and_defer(client, identities, frozen, financial_store):
    pid, rows, _ = frozen
    c = language(rows)
    submit(client, identities[0], pid, c)
    submit(client, identities[1], pid, c, language="ISSUER_ATTRIBUTION")
    s = state(financial_store, pid, c["id"])
    url = endpoint(pid, c["id"])
    h = headers(identities[3], "synthetic-resolution-retry")
    assert client.post(url, headers=headers(identities[0]), json=decision(s)).status_code == 403
    assert client.post(url, headers=h, json=decision(s)).status_code == 200
    assert client.post(url, headers=h, json=decision(s)).json()["version"] == 1
    assert state(financial_store, pid, c["id"])["status"] == "ADJUDICATED"
    submit(
        client,
        identities[0],
        pid,
        c,
        expected_version=1,
        reason="Updated evidence rationale for synthetic test",
    )
    changed = state(financial_store, pid, c["id"])
    assert changed["status"] == "DISAGREEMENT" and changed["stale_adjudication"]
    assert client.post(url, headers=headers(identities[3]), json=decision(s)).status_code == 409
    deferred = decision(changed, outcome="DEFERRED", language=None)
    assert client.post(url, headers=headers(identities[3]), json=deferred).status_code == 200
    assert state(financial_store, pid, c["id"])["status"] == "ADJUDICATION_DEFERRED"
    assert state(financial_store, pid, c["id"])["gold"] is None
    with financial_store.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(adjudications)) == 2
        assert conn.scalar(select(func.count()).select_from(labels)) == 3
    exported = client.get(
        f"/api/v0/admin/evaluation/{pid}/export", headers=headers(identities[3])
    ).json()
    assert len(exported["adjudication_revisions"]) == 2
    assert len(exported["label_revisions"]) == 3
    assert exported["quality"]["gold_cases"] == 0
    assert (
        client.get(
            f"/api/v0/admin/evaluation/{pid}/export", headers=headers(identities[0])
        ).status_code
        == 403
    )


def test_self_review_and_missing_votes_rejected(client, identities, frozen, financial_store):
    pid, rows, _ = frozen
    c = language(rows)
    s = state(financial_store, pid, c["id"])
    assert (
        client.post(
            endpoint(pid, c["id"]), headers=headers(identities[3]), json=decision(s)
        ).status_code
        == 409
    )
    submit(client, identities[0], pid, c)
    submit(client, identities[3], pid, c, language="ISSUER_ATTRIBUTION")
    s = state(financial_store, pid, c["id"])
    assert (
        client.post(
            endpoint(pid, c["id"]), headers=headers(identities[3]), json=decision(s)
        ).status_code
        == 403
    )


def numeric(value="120"):
    return {
        "verdict": "COMPARABLE",
        "unit": "USD",
        "current_value": value,
        "prior_value": "100",
        "current_start": "2026-04-01",
        "current_end": "2026-06-30",
        "prior_start": "2025-04-01",
        "prior_end": "2025-06-30",
    }


@pytest.mark.parametrize(
    "amount", ["1e999999999", "1e-999999999", "1000000000000000000000000000001"]
)
def test_numeric_bounds_do_not_round_or_overflow(amount):
    from engine.api.annotations import Numeric

    with pytest.raises(ValueError):
        Numeric.model_validate(numeric(amount))
    assert Numeric.model_validate(numeric("1e30")).current_value == "1e30"


@pytest.mark.parametrize(
    "left,right,equal",
    [
        ("120", "120.0", True),
        ("0", "-0", True),
        ("120", "121", False),
        ("1", "1.000000000000000000000000000001", False),
        ("123456789012345678901234567890", "123456789012345678901234567891", False),
    ],
)
def test_decimal_equivalence(left, right, equal):
    assert (
        normalized({"numeric": numeric(left)}) == normalized({"numeric": numeric(right)})
    ) == equal


def test_numeric_period_conflicts_and_wrong_resolution_type(
    client, identities, frozen, financial_store
):
    pid, rows, _ = frozen
    c = next(c for c in rows if c["kind"] == "segment_comparison")
    assert (
        submit(
            client, identities[0], pid, c, language=None, numeric=numeric("1e-1000000000")
        ).status_code
        == 422
    )
    submit(client, identities[0], pid, c, language=None, numeric=numeric())
    submit(client, identities[1], pid, c, language=None, numeric=numeric("120.0"))
    assert state(financial_store, pid, c["id"])["status"] == "CONSENSUS"
    submit(
        client,
        identities[1],
        pid,
        c,
        expected_version=1,
        language=None,
        numeric={**numeric(), "prior_start": "2025-03-01"},
    )
    s = state(financial_store, pid, c["id"])
    assert s["status"] == "DISAGREEMENT"
    url = endpoint(pid, c["id"])
    assert client.post(url, headers=headers(identities[3]), json=decision(s)).status_code == 422
    assert (
        client.post(
            url, headers=headers(identities[3]), json=decision(s, language=None, numeric=numeric())
        ).status_code
        == 200
    )


def test_freeze_integrity_and_pending_metrics(client, identities, frozen, financial_store):
    pid, rows, pack = frozen
    assert freeze(financial_store, pack)["status"] == "duplicate"
    altered = copy.deepcopy(pack)
    altered["predictions"][rows[0]["id"]] = "tampered"
    with pytest.raises(ValueError):
        freeze(financial_store, altered)
    with financial_store.connect() as conn:
        report = quality(conn, pid)
    assert report["status"] == "PENDING_LABELS" and report["gold_cases"] == 0
    assert all(m["accuracy_on_resolved"] is None for m in report["holdout"].values())
    assert (
        client.get(
            f"/api/v0/admin/evaluation/{pid}/quality", headers=headers(identities[0])
        ).status_code
        == 403
    )
    response = client.get(
        f"/api/v0/admin/evaluation/{pid}/cases/{rows[0]['id']}", headers=headers(identities[3])
    ).json()
    assert "predictions" not in str(response)


def test_freeze_after_labels_rejected(client, identities, assigned, financial_store):
    pid, rows = assigned
    with financial_store.connect() as conn:
        pack = packet(conn, datetime.fromisoformat(rows[0]["as_of"]))
    submit(client, identities[0], pid, language(rows))
    with pytest.raises(ValueError, match="before any labels"):
        freeze(financial_store, pack)


def test_holdout_scoring_and_invalidation(client, identities, frozen, financial_store):
    pid, rows, pack = frozen
    # Synthetic test database only: promote fixture cases to holdout to exercise scoring.
    with financial_store.begin() as conn:
        for c in rows:
            conn.execute(
                cases.update()
                .where(cases.c.packet_id == pid, cases.c.id == c["id"])
                .values(payload={**c, "split": "holdout"})
            )
    c = language(rows)
    truth = pack["predictions"][c["id"]]
    for user in identities[:2]:
        submit(client, user, pid, c, language=truth)
    with financial_store.connect() as conn:
        report = quality(conn, pid)
    assert report["status"] == "PARTIAL_HOLDOUT"
    m = report["holdout"]["causal_language"]
    assert m["scored"] == m["correct"] == 1 and m["accuracy_on_resolved"] == 1
    assert m["coverage"] == 1 / 3 and m["consensus"] == 1
    assert report["holdout"]["segment_comparison"]["accuracy_on_resolved"] is None
    n = next(c for c in rows if c["kind"] == "segment_comparison")
    from engine.evaluation.consensus import predicted

    operands = predicted(n, pack["predictions"][n["id"]])["numeric"]
    for user in identities[:2]:
        assert submit(client, user, pid, n, language=None, numeric=operands).status_code == 200
    submit(
        client,
        identities[1],
        pid,
        c,
        expected_version=1,
        language="NO_CAUSAL_CLAIM" if truth != "NO_CAUSAL_CLAIM" else "ISSUER_ATTRIBUTION",
    )
    s = state(financial_store, pid, c["id"])
    assert (
        client.post(
            endpoint(pid, c["id"]), headers=headers(identities[3]), json=decision(s, language=truth)
        ).status_code
        == 200
    )
    with financial_store.connect() as conn:
        report = quality(conn, pid)
    assert report["holdout"]["segment_comparison"]["accuracy_on_resolved"] == 1
    assert report["holdout"]["causal_language"]["adjudicated"] == 1
    assert report["agreement"]["causal_language"]["rate"] == 0
    from engine.filing_evidence import snapshots as filing_snapshots

    with financial_store.begin() as conn:
        conn.execute(filing_snapshots.delete())
    with financial_store.connect() as conn:
        changed = quality(conn, pid)
    assert changed["holdout"]["causal_language"]["scored"] == 0
    assert changed["holdout"]["causal_language"]["source_excluded"] == 3
    assert changed["evaluation_input_sha256"] != report["evaluation_input_sha256"]
    assert (
        client.post(
            endpoint(pid, c["id"]),
            headers=headers(identities[3]),
            json=decision(state(financial_store, pid, c["id"])),
        ).status_code
        == 409
    )


def test_gateway_keeps_adjudication_local():
    from engine.mobile_gateway import allowed

    assert not allowed("GET", "/adjudicate")
    for method in ("GET", "POST"):
        assert not allowed(method, "/api/v0/admin/evaluation/packets")
        assert not allowed(method, "/api/v0/admin/evaluation/" + "a" * 64 + "/quality")
        assert not allowed(method, endpoint("a" * 64, "b" * 64))
