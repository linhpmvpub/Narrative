"""Latest independent votes, revision-bound adjudication and frozen-prediction metrics."""

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations
from pathlib import Path

from sqlalchemy import select

from engine.annotations import source_status
from engine.evaluation.filing_labels import packet
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v10 import cases, labels, packets
from engine.models.schema_v11 import adjudications, predictions


def normalized(payload):
    if payload.get("language") is not None:
        return {"language": payload["language"]}
    n = payload["numeric"]
    result = {"verdict": n["verdict"]}
    if n["verdict"] == "COMPARABLE":
        result.update(
            {k: n[k] for k in ("unit", "current_start", "current_end", "prior_start", "prior_end")}
        )
        for key in ("current_value", "prior_value"):
            value = Decimal(n[key])
            # normalize() rounds to the ambient decimal precision; preserve every digit.
            rendered = format(value, "f") if value else "0"
            result[key] = rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
    return {"numeric": result}


def freeze(engine, sealed):
    ordered = sorted(sealed["cases"], key=lambda c: c["id"])
    pid = digest(ordered)
    cutoff = datetime.fromisoformat(sealed["as_of"])
    if cutoff.tzinfo is None or cutoff > datetime.now(UTC):
        raise ValueError("Invalid frozen cutoff")
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        conn.execute(select(database_mode).with_for_update()).one()
        stored = sorted(
            conn.execute(select(cases.c.payload).where(cases.c.packet_id == pid)).scalars(),
            key=lambda c: c["id"],
        )
        if stored != ordered:
            raise ValueError("Packet not imported or frozen cases differ")
        expected = packet(conn, cutoff)
        if (
            sealed["predictions"] != expected["predictions"]
            or sealed["extractor"] != expected["extractor"]
        ):
            raise ValueError("Predictions do not match original source extraction")
        payload = {
            "predictions": sealed["predictions"],
            "extractor": sealed["extractor"],
            "as_of": sealed["as_of"],
        }
        sha = digest(payload)
        old = (
            conn.execute(select(predictions).where(predictions.c.packet_id == pid))
            .mappings()
            .first()
        )
        if old:
            if old["sha256"] != sha:
                raise ValueError("Frozen predictions are immutable")
            return {"packet_id": pid, "status": "duplicate", "sha256": sha}
        if conn.scalar(select(labels.c.id).where(labels.c.packet_id == pid).limit(1)):
            raise ValueError("Freeze predictions before any labels are submitted")
        conn.execute(
            predictions.insert().values(
                packet_id=pid, payload=payload, sha256=sha, frozen_at=datetime.now(UTC)
            )
        )
    return {"packet_id": pid, "status": "frozen", "sha256": sha}


def states(conn, pid):
    if not conn.scalar(select(packets.c.id).where(packets.c.id == pid)):
        raise ValueError("Packet not found")
    votes: dict = defaultdict(dict)
    for row in conn.execute(
        select(labels).where(labels.c.packet_id == pid).order_by(labels.c.version)
    ).mappings():
        votes[row["case_id"]][row["user_id"]] = dict(row)
    resolutions = {}
    for row in conn.execute(
        select(adjudications)
        .where(adjudications.c.packet_id == pid)
        .order_by(adjudications.c.version)
    ).mappings():
        resolutions[row["case_id"]] = dict(row)
    result, source_cache = [], {}
    for c in conn.execute(
        select(cases.c.payload).where(cases.c.packet_id == pid).order_by(cases.c.id)
    ).scalars():
        current_votes = sorted(votes[c["id"]].values(), key=lambda v: v["user_id"])
        sid = c["snapshot_id"]
        if sid not in source_cache:
            source_cache[sid] = source_status(conn, c)
        status = source_cache[sid]
        fingerprint = digest(
            [c["id"], c["source_sha256"], status, [(v["id"], v["version"]) for v in current_votes]]
        )
        decision = resolutions.get(c["id"])
        state = {
            "case": c,
            "source_status": status,
            "votes": current_votes,
            "vote_hash": fingerprint,
            "decision_version": decision["version"] if decision else 0,
            "gold": None,
            "stale_adjudication": bool(decision and decision["vote_hash"] != fingerprint),
            "decision": decision,
        }
        if status != "CURRENT":
            state["status"] = "SOURCE_EXCLUDED"
        elif any(
            v["payload"].get("independent_of_extractor") is not True
            or v["payload"].get("source_sha256") != c["source_sha256"]
            or v["payload"].get("reviewer") != v["user_id"]
            for v in current_votes
        ):
            state["status"] = "INVALID_LABELS"
        elif len(current_votes) < 2:
            state["status"] = "WAITING_FOR_TWO_REVIEWERS"
        elif len({digest(normalized(v["payload"])) for v in current_votes}) == 1:
            state["status"] = "CONSENSUS"
            state["gold"] = normalized(current_votes[0]["payload"])
        elif (
            decision
            and decision["vote_hash"] == fingerprint
            and decision["reviewer_id"] not in votes[c["id"]]
        ):
            state["status"] = (
                "ADJUDICATED"
                if decision["payload"]["outcome"] == "RESOLVED"
                else "ADJUDICATION_DEFERRED"
            )
            if state["status"] == "ADJUDICATED":
                state["gold"] = normalized(decision["payload"])
        else:
            state["status"] = "DISAGREEMENT"
        result.append(state)
    return result


def predicted(case, value):
    if case["kind"] == "causal_language":
        return {"language": value}
    numeric = {"verdict": "COMPARABLE", "unit": value["unit"]}
    for side in ("current", "prior"):
        for key in ("value", "start", "end"):
            numeric[side + "_" + key] = value[side][key]
    return normalized({"numeric": numeric})


def quality(conn, pid):
    results = states(conn, pid)
    frozen = (
        conn.execute(select(predictions).where(predictions.c.packet_id == pid)).mappings().first()
    )
    counts = dict(Counter(s["status"] for s in results))
    report = {
        "packet_id": pid,
        "total_cases": len(results),
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluation_input_sha256": digest(
            [[s["case"]["id"], s["vote_hash"], s["decision_version"], s["status"]] for s in results]
        ),
        "states": counts,
        "gold_cases": sum(s["gold"] is not None for s in results),
        "prediction_sha256": frozen["sha256"] if frozen else None,
        "prediction_frozen_at": utc(frozen["frozen_at"]).isoformat() if frozen else None,
        "status": "PENDING_LABELS",
        "holdout": {},
        "agreement": {},
        "delivery": "disabled",
        "graph_modified": False,
        "market_prediction_accuracy": None,
        "limitations": [
            "Metrics only cover sampled language classification and extracted numeric comparisons",
            "Numeric cases contain extracted positives: extraction recall cannot be estimated",
            "Consensus is human reference data, not scientific causal identification",
            "Account independence is declared, not independently identity-verified",
            "Corpus was visible during development; use unseen periods before generalization claims",
        ],
    }
    for kind in ("causal_language", "segment_comparison"):
        selected = [s for s in results if s["case"]["kind"] == kind]
        pairs = [
            (normalized(a["payload"]), normalized(b["payload"]))
            for s in selected
            if s["source_status"] == "CURRENT" and s["status"] != "INVALID_LABELS"
            for a, b in combinations(s["votes"], 2)
        ]
        report["agreement"][kind] = {
            "reviewer_pairs": len(pairs),
            "agreeing_pairs": sum(a == b for a, b in pairs),
            "rate": sum(a == b for a, b in pairs) / len(pairs) if pairs else None,
            "basis": "latest raw votes before adjudication; pair-weighted across all current cases",
        }
        held = [s for s in selected if s["case"]["split"] == "holdout"]
        resolved = [s for s in held if s["gold"] is not None]
        scored = []
        if frozen:
            for s in resolved:
                # Refuse quality claims if imports/database tampering put any vote before the freeze.
                if any(utc(v["created_at"]) < utc(frozen["frozen_at"]) for v in s["votes"]):
                    continue
                model = frozen["payload"]["predictions"].get(s["case"]["id"])
                if model is not None:
                    scored.append((predicted(s["case"], model), s["gold"]))
        confusion: dict = {}
        if kind == "causal_language":
            for guess, gold in scored:
                truth = gold["language"]
                confusion.setdefault(truth, {})
                confusion[truth][guess["language"]] = confusion[truth].get(guess["language"], 0) + 1
        correct = sum(guess == gold for guess, gold in scored)
        report["holdout"][kind] = {
            "total": len(held),
            "source_excluded": sum(s["status"] == "SOURCE_EXCLUDED" for s in held),
            "resolved": len(resolved),
            "scored": len(scored),
            "correct": correct,
            "coverage": len(scored) / len(held) if held else None,
            "accuracy_on_resolved": correct / len(scored) if scored else None,
            "consensus": sum(s["status"] == "CONSENSUS" for s in resolved),
            "adjudicated": sum(s["status"] == "ADJUDICATED" for s in resolved),
            "confusion_gold_rows_prediction_columns": confusion,
        }
    total = sum(m["total"] for m in report["holdout"].values())
    scored_count = sum(m["scored"] for m in report["holdout"].values())
    report["status"] = (
        "PREDICTIONS_NOT_FROZEN"
        if not frozen
        else "COMPLETE_HOLDOUT"
        if total and scored_count == total
        else "PARTIAL_HOLDOUT"
        if scored_count
        else "PENDING_LABELS"
    )
    return report


def main():
    import argparse

    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--report-packet")
    args = parser.parse_args()
    engine = database()
    try:
        if args.freeze:
            print(
                json.dumps(
                    freeze(engine, json.loads(args.freeze.read_text(encoding="utf-8"))), indent=2
                )
            )
        elif args.report_packet:
            with engine.connect() as conn:
                print(json.dumps(quality(conn, args.report_packet), indent=2))
        else:
            parser.error("Specify --freeze or --report-packet")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
