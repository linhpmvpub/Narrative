"""Local hash-chained R05 reviews. Trusted operator store, not remote authentication."""

import argparse
import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from engine.ingestion.contracts import digest
from engine.structured_news import normalized


class Facet(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    event_term: str = Field(min_length=1, max_length=300)
    exposure_term: str = Field(min_length=1, max_length=300)


class Vote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_id: str = Field(min_length=1, max_length=100)
    proposal_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["APPROVE", "REJECT", "UNSURE"]
    reviewed_at: AwareDatetime


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    author_id: str = Field(min_length=1, max_length=100)
    event_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    selection_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    atlas_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    playbook_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_epoch: int = Field(ge=1)
    narrative_id: str
    route: list[str] = Field(min_length=1, max_length=5)
    identity_reference_id: str
    source_id: str
    exposure_quote: str = Field(min_length=1, max_length=8000)
    facets: dict[str, Facet]
    effective_from: AwareDatetime
    effective_until: AwareDatetime
    created_at: AwareDatetime
    review_until: AwareDatetime


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal: Proposal
    votes: list[Vote] = Field(max_length=10)
    status: Literal["REVIEWED", "DISPUTED", "REVOKED"]
    recorded_at: AwareDatetime


class Store:
    """Transactions serialize appends; expected head prevents stale concurrent writers.

    Hash chains detect row edits/gaps, not full-store rollback by a privileged operator.
    No HTTP endpoint. Reviewer identities and source notices are operator-maintained.
    """

    def __init__(self, path, *, create=False):
        self.path = Path(path)
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self.connect()) as conn, conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL, previous TEXT, hash TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id,version))"
                )
        elif not self.path.is_file():
            raise ValueError("Scope review store missing")

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def history(self, kind, identity, conn=None):
        if conn is None:
            with closing(self.connect()) as own:
                return self.history(kind, identity, own)
        rows = conn.execute(
            "SELECT version,previous,hash,payload FROM records WHERE kind=? AND id=? ORDER BY version",
            (kind, identity),
        ).fetchall()
        if len(rows) > 1000:
            raise ValueError("Review history limit exceeded")
        result: list[dict] = []
        previous = None
        for version, parent, sha, raw in rows:
            value = json.loads(raw)
            expected = digest([kind, identity, version, parent, value])
            if version != len(result) + 1 or parent != previous or sha != expected:
                raise ValueError("Review/source history integrity failed")
            result.append({"version": version, "sha256": sha, "payload": value})
            previous = sha
        return result

    def append(self, kind, identity, value, *, expected_head=None):
        if kind not in {"source", "review"} or not identity or len(identity) > 200:
            raise ValueError("Invalid ledger identity")
        if kind == "review":
            review = Review.model_validate(value)
            if review.proposal.id != identity or review.recorded_at > datetime.now(UTC):
                raise ValueError("Review identity/time invalid")
            value = review.model_dump(mode="json")
        else:
            if (
                set(value) != {"packet_sha256", "status", "observed_at"}
                or value["status"] not in {"CURRENT", "WITHDRAWN", "DISPUTED"}
                or not re.fullmatch(r"[a-f0-9]{64}", value["packet_sha256"])
            ):
                raise ValueError("Explicit source state required")
            time = datetime.fromisoformat(value["observed_at"])
            if time.tzinfo is None or time > datetime.now(UTC):
                raise ValueError("Source observation time invalid")
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            history = self.history(kind, identity, conn)
            previous = history[-1]["sha256"] if history else None
            if previous != expected_head:
                raise ValueError("Stale ledger head; reread before appending")
            time_key = "recorded_at" if kind == "review" else "observed_at"
            if history and datetime.fromisoformat(value[time_key]) < datetime.fromisoformat(
                history[-1]["payload"][time_key]
            ):
                raise ValueError("Ledger timestamps must not go backwards")
            version = len(history) + 1
            sha = digest([kind, identity, version, previous, value])
            conn.execute(
                "INSERT INTO records VALUES(?,?,?,?,?,?)",
                (kind, identity, version, previous, sha, json.dumps(value)),
            )
        return {"version": version, "sha256": sha}

    def fingerprint(self):
        with closing(self.connect()) as conn:
            rows = conn.execute(
                "SELECT kind,id,version,previous,hash,payload FROM records ORDER BY kind,id,version LIMIT 10001"
            ).fetchall()
        if len(rows) > 10000:
            raise ValueError("Ledger size limit exceeded")
        return digest(rows)


def check(store, identity, policy, data, frame, selection, path, book, at):
    """A review approves exactly one path's literal scope, never its economic magnitude."""
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Nonfuture aware evaluation cutoff required")
    history = store.history("review", identity)
    if not history:
        raise ValueError("Review not found")
    record = history[-1]
    review = Review.model_validate(record["payload"])
    p = review.proposal
    if (
        review.status != "REVIEWED"
        or review.recorded_at > at
        or p.event_sha256 != digest(frame.model_dump(mode="json"))
        or p.selection_sha256 != digest(selection)
        or p.atlas_sha256 != digest(data)
        or p.playbook_sha256 != digest(book)
        or p.route != path["relations"]
        or p.narrative_id != path["narrative_id"]
        or not frame.reviewed_at <= p.created_at <= review.recorded_at <= at < p.review_until
        or not 0 < (p.review_until - p.created_at).total_seconds() <= 90 * 86400
        or not p.effective_from < p.effective_until <= p.created_at
    ):
        raise ValueError("Review revoked, stale, expired, future or differently scoped")
    sources = store.history("source", selection["revision"]["id"])
    if not sources:
        raise ValueError("Current source state not registered")
    current = sources[-1]
    if (
        current["version"] != p.source_epoch
        or current["payload"]["status"] != "CURRENT"
        or current["payload"]["packet_sha256"] != selection["packet_sha256"]
        or not datetime.fromisoformat(current["payload"]["observed_at"]) <= p.created_at
    ):
        raise ValueError("Source changed, withdrawn or disputed; new review required")
    edges = {r["id"]: r for r in data["relations"]}
    for rid in p.route:
        edge = edges.get(rid)
        if (
            edge is None
            or not edge["eligible_at_snapshot"]
            or edge["status"] != "SOURCE_BACKED"
            or datetime.fromisoformat(edge["valid_from"]) > p.effective_from
            or (
                edge["valid_until"] is not None
                and datetime.fromisoformat(edge["valid_until"]) < p.effective_until
            )
        ):
            raise ValueError("Relationship not valid over reviewed event interval")
    anchor = edges[p.route[0]]
    if anchor["from_id"] != frame.factor_id or not any(
        e["source_id"] == p.source_id and p.exposure_quote in e["quote"] for e in anchor["evidence"]
    ):
        raise ValueError("Exposure quote not on upstream anchoring relationship")
    ref = next((x for x in data["entity_references"] if x["id"] == p.identity_reference_id), None)
    if (
        ref is None
        or not ref["eligible_at_snapshot"]
        or ref["status"] != "SOURCE_BACKED"
        or ref["resolution"] != "EXACT_ENTITY"
        or ref["identity_level"] != "LEGAL_ENTITY"
        or ref["node_id"] != frame.factor_id
        or anchor["id"] not in ref["relationship_ids"]
        or not datetime.fromisoformat(ref["reviewed_at"]) <= p.created_at
        or at >= datetime.fromisoformat(ref["review_until"])
    ):
        raise ValueError("Upstream legal identity unavailable or expired")
    if set(p.facets) != {"legal_entity", "product", "facility", "geography", "period"}:
        raise ValueError("All five explicit scope facets required")
    for name, facet in p.facets.items():
        if not re.search(
            r"(?<!\w)" + re.escape(facet.event_term) + r"(?!\w)", frame.source_quote
        ) or not re.search(
            r"(?<!\w)" + re.escape(facet.exposure_term) + r"(?!\w)", p.exposure_quote
        ):
            raise ValueError("Scope term missing from pinned source quote")
        if name == "legal_entity":
            if not {normalized(facet.event_term), normalized(facet.exposure_term)} <= {
                normalized(n) for n in ref["names"]
            }:
                raise ValueError("Legal names not authorized by identity reference")
        elif normalized(facet.event_term) != normalized(facet.exposure_term):
            raise ValueError("Only exact literal scope supported in R05v1")
    if not isinstance(policy, dict) or set(policy) != {"reviewers"}:
        raise ValueError("Explicit trusted local reviewer policy required")
    reviewers = policy["reviewers"]
    if not isinstance(reviewers, dict):
        raise ValueError("Reviewer policy must map identities to roles")
    seen = set()
    if len(review.votes) < 2:
        raise ValueError("Two independent review votes required")
    for vote in review.votes:
        role = reviewers.get(vote.reviewer_id)
        if (
            vote.reviewer_id in seen
            or vote.reviewer_id in {p.author_id, frame.reviewer_id}
            or role not in {"HUMAN", "AI_INDEPENDENT"}
            or vote.decision != "APPROVE"
            or vote.proposal_sha256 != digest(p.model_dump(mode="json"))
            or not p.created_at <= vote.reviewed_at <= review.recorded_at
        ):
            raise ValueError("Missing, conflicting, unauthorized or self-review vote")
        seen.add(vote.reviewer_id)
    return {
        "status": "PASS",
        "review_id": identity,
        "version": record["version"],
        "review_sha256": record["sha256"],
        "reviewers": sorted(seen),
        "source_epoch": p.source_epoch,
        "scope_basis": "TWO_REVIEWER_LITERAL_SCOPE",
        "human_gold": False,
        "reviewer_kinds": {x: reviewers[x] for x in seen},
        "reviewer_policy_sha256": digest(policy),
        "financial_magnitude": "UNKNOWN",
        "delivery": "disabled",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "append", "history", "proposal-hash"])
    parser.add_argument("--store", type=Path)
    parser.add_argument("--kind", choices=["source", "review"])
    parser.add_argument("--id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--expected-head")
    args = parser.parse_args()
    if args.action == "proposal-hash":
        if args.input is None:
            parser.error("--input required")
        proposal = Proposal.model_validate_json(args.input.read_bytes())
        print(json.dumps({"proposal_sha256": digest(proposal.model_dump(mode="json"))}))
        return
    if args.store is None:
        parser.error("--store required")
    store = Store(args.store, create=args.action == "init")
    if args.action == "init":
        result = {"initialized": True}
    else:
        if not args.kind or not args.id:
            parser.error("--kind and --id required")
        if args.action == "append":
            if args.input is None:
                parser.error("--input required")
            result = store.append(
                args.kind,
                args.id,
                json.loads(args.input.read_text(encoding="utf-8")),
                expected_head=args.expected_head,
            )
        else:
            result = store.history(args.kind, args.id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
