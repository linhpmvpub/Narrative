"""Explicit offline freeze pipeline. No database, notifications or agent invocation."""

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

from engine.adapters.http_sources import SourceClient
from engine.collect_sec import candidates, collect, identities
from engine.evaluation.language_audit import screen_future, signature
from engine.evaluation.language_candidate import VERSION, classify
from engine.ingestion.contracts import digest
from engine.settings import Settings


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def capture(root, name, expected):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Capture path escapes collection")
    text = path.read_text(encoding="utf-8")
    if hashlib.sha256(text.encode()).hexdigest() != expected:
        raise ValueError("Capture hash mismatch")
    return text


class Paragraphs(HTMLParser):
    """Visible block text, including negatives; never select using model predictions."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.rows: list[str] = []
        self.hidden = 0

    def flush(self):
        text = " ".join(" ".join(self.parts).split())
        if 40 <= len(text) <= 4000:
            self.rows.append(text)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "ix:hidden", "head"}:
            self.hidden += 1
        if not self.hidden and tag in {"p", "div", "tr", "li", "br"}:
            self.flush()

    def handle_endtag(self, tag):
        if tag in {"script", "style", "ix:hidden", "head"}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in {"p", "div", "tr", "li"}:
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def collect_new(client, output, plan, now=None):
    now = now or datetime.now(UTC)
    start = datetime.fromisoformat(plan["frozen_at"]).date() + timedelta(days=1)
    if start > now.date():
        return {"status": "WAITING_FOR_ELIGIBLE_FILING_DATE", "earliest_date": str(start)}
    return collect(client, output, start, now.date(), per_company=20)


def prepare(collection, plan, output, *, per_filing=20, now=None):
    now = now or datetime.now(UTC)
    if not 1 <= per_filing <= 100:
        raise ValueError("per_filing must be 1..100")
    if output.exists():
        raise ValueError("Run already exists; verify it or use a new directory")
    manifest = read(collection / "collection.json")
    if manifest.get("errors"):
        raise ValueError("Incomplete collection; resolve source errors before freezing")
    issuers = identities(
        json.loads(capture(collection, "company_tickers.json", manifest["index_sha256"]))
    )
    if set(manifest["identities"]) != set(issuers):
        raise ValueError("Incomplete issuer collection")
    selected: list[dict] = []
    rejected: list[dict] = []
    seen: list[dict] = []
    for filing in sorted(manifest["filings"], key=lambda f: (f["ticker"], f["accession"])):
        ticker = filing["ticker"]
        identity = manifest["identities"][ticker]
        if identity["cik"] != issuers[ticker]["cik"]:
            raise ValueError("Identity mismatch")
        payload = json.loads(
            capture(collection, ticker + "-submissions.json", identity["submission_sha256"])
        )
        rows = candidates(ticker, identity["cik"], payload, date.min, now.date(), 10000)
        if not any(
            all(filing[k] == row[k] for k in ("url", "cik", "accession", "form", "filing_date"))
            for row in rows
        ):
            raise ValueError("Filing disagrees with captured SEC submissions")
        text = capture(collection, filing["file"], filing["content_sha256"])
        parser = Paragraphs()
        parser.feed(text)
        parser.flush()
        accepted = 0
        # Stable, label-independent sampling includes non-financial paragraphs.
        for paragraph in sorted(set(parser.rows), key=lambda t: digest(t)):
            case = {
                "id": digest([ticker, filing["accession"], filing["content_sha256"], paragraph]),
                "kind": "causal_language",
                "split": "holdout",
                "ticker": ticker,
                "accession": filing["accession"],
                "source_sha256": filing["content_sha256"],
                "url": filing["url"],
                "filing_date": filing["filing_date"],
                "available_at": filing["retrieved_at"],
                "text": paragraph,
            }
            gate = screen_future(case, {**plan, "seen_text": plan["seen_text"] + seen}, now)
            if not gate["eligible_for_new_review"]:
                rejected.append({"case_id": case["id"], "reasons": gate["reasons"]})
                continue
            if accepted >= per_filing:
                rejected.append({"case_id": case["id"], "reasons": ["SAMPLING_CAP"]})
                continue
            seen.append(signature(paragraph))
            selected.append(case)
            accepted += 1
    if not selected:
        raise ValueError("No eligible cases; no predictions or blind packet created")
    selected.sort(key=lambda c: c["id"])
    pid = digest(selected)
    pack = {"evaluation_track": "AI_SIMULATED", "packet_id": pid, "cases": selected}
    sealed = {
        "cases": selected,
        "predictions": {c["id"]: classify(c["text"])["label"] for c in selected},
        "extractor": VERSION,
        "as_of": now.isoformat(),
    }
    receipt = {
        "packet_id": pid,
        "prediction_sha256": digest({k: sealed[k] for k in ("predictions", "extractor", "as_of")}),
        "protocol_sha256": digest(plan),
        "frozen_at": now.isoformat(),
        "collection_sha256": digest(manifest),
        "candidate_sha256": plan["candidate_sha256"],
        "cases": len(selected),
        "rejections": rejected,
        "per_filing": per_filing,
        "delivery": "disabled",
        "promotion_allowed": False,
    }
    # An interrupted run never exposes a release-ready packet.
    staging = output.with_name(output.name + ".pending")
    staging.mkdir(parents=True, exist_ok=False)
    write(staging / "sealed-predictions.json", sealed)
    write(staging / "blind-input.json", pack)
    write(staging / "receipt.json", receipt)
    write(staging / "protocol.json", plan)
    staging.rename(output)
    return receipt


def verify(output):
    from engine.evaluation.language_audit import verify_baseline

    receipt, sealed = read(output / "receipt.json"), read(output / "sealed-predictions.json")
    pack, plan = read(output / "blind-input.json"), read(output / "protocol.json")
    verify_baseline(sealed, receipt)
    if (
        pack
        != {
            "evaluation_track": "AI_SIMULATED",
            "packet_id": receipt["packet_id"],
            "cases": sealed["cases"],
        }
        or digest(plan) != receipt["protocol_sha256"]
    ):
        raise ValueError("Blind packet or protocol changed")
    return {"packet_id": receipt["packet_id"], "cases": receipt["cases"], "integrity": "verified"}


def review_run(output, reviews, action):
    from engine.evaluation.agent_pilot import disputes, evaluate

    verify(output)
    pack = read(output / "blind-input.json")
    left, right = read(reviews / "reviewer-a.json"), read(reviews / "reviewer-b.json")
    if action == "disputes":
        value = disputes(pack, left, right)
        target = reviews / "disputes.json"
    else:
        value = evaluate(
            pack,
            left,
            right,
            read(output / "sealed-predictions.json"),
            read(reviews / "expert.json"),
        )
        target = reviews / "summary.json"
    if target.exists():
        if read(target) != value and action == "disputes":
            raise ValueError("Existing dispute packet differs")
        if action != "disputes":
            raise ValueError("Summary already exists; preserve it and use a new review directory")
    else:
        write(target, value)
    return {"packet_id": pack["packet_id"], "artifact": target.name, "delivery": "disabled"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["collect", "prepare", "verify", "disputes", "evaluate"])
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("source-cache/language-audit-v2.0.1/prospective-protocol.json"),
    )
    parser.add_argument("--collection", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--user-agent")
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--per-filing", type=int, default=20)
    args = parser.parse_args()
    Settings.from_env()
    if args.action in {"disputes", "evaluate"}:
        if args.reviews is None:
            parser.error("review actions require --reviews")
        result = review_run(args.output, args.reviews, args.action)
    elif args.action == "verify":
        result = verify(args.output)
    elif args.action == "collect":
        client = SourceClient(user_agent=args.user_agent or "")
        try:
            result = collect_new(client, args.output, read(args.protocol))
            result = {k: v for k, v in result.items() if k in {"status", "earliest_date", "errors"}}
        finally:
            client.close()
    else:
        if args.collection is None:
            parser.error("prepare requires --collection")
        receipt = prepare(
            args.collection, read(args.protocol), args.output, per_filing=args.per_filing
        )
        result = {k: receipt[k] for k in ("packet_id", "cases", "delivery")}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
