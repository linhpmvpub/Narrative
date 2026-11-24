"""Local operator queue and pinned replacement review packets; never auto-approve."""
import argparse
import copy
import difflib
import html
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from engine.adapters.news import NewsClient, canonical_url
from engine.article_feed import anchors, approve_replacement, root_dir
from engine.company_profiles import writer_lock
from engine.evaluation.article_relevance import utc
from engine.ingestion.contracts import digest
from engine.news_articles import capture, read_packet


def state_at(root):
    state = json.loads((root / "current.json").read_text(encoding="utf-8"))
    if state["schema"] != "ARTICLE_FEED_V1" or not 1 <= len(state["entries"]) <= 100:
        raise ValueError("Invalid bounded feed state")
    return state


def queue(conn, *, root=None):
    root = Path(root) if root is not None else root_dir()
    with writer_lock(root):
        state = state_at(root)
        rows = []
        for entry in state["entries"]:
            selection = entry["selection"]
            url = selection["revision"]["payload"]["url"]
            reasons = [] if entry["status"] == "ACTIVE" else [entry["status"]]
            try:
                if anchors(conn, url) != entry["anchors"]:
                    reasons.append("INBOX_CHANGED")
            except ValueError:
                reasons.append("INBOX_BLOCKED")
            if entry["status"] == "ACTIVE":
                try:
                    if not datetime.now(UTC) - timedelta(hours=1) <= utc(entry["checked_at"]) <= datetime.now(UTC):
                        reasons.append("PROOF_EXPIRED")
                except (ValueError, TypeError):
                    reasons.append("PROOF_INVALID")
            if reasons:
                rows.append({"url": url, "title": selection["revision"]["payload"]["title"],
                             "reasons": reasons, "entry_sha256": digest(entry),
                             "action": "RECHECK" if set(reasons) <= {
                                 "UNAVAILABLE", "CHECKING", "AWAITING_RECHECK", "PROOF_EXPIRED"
                             } else "EXPLICIT_BODY_REVIEW"})
    return {"version": state["version"], "items": rows, "delivery": "disabled"}


def prepare(conn, client, url, output, *, root=None):
    """Capture anew, pin entry/inbox, export inert diff and an intentionally invalid draft."""
    root = Path(root) if root is not None else root_dir()
    output = Path(output)
    with writer_lock(root):
        state = state_at(root)
        entry = next((e for e in state["entries"] if canonical_url(
            e["selection"]["revision"]["payload"]["url"]) == canonical_url(url)), None)
        if entry is None:
            raise ValueError("Unknown article")
        pinned = anchors(conn, url)  # Publisher withdrawal blocks preparation too.
        selection = copy.deepcopy(entry["selection"])
        revision = {**selection["revision"], "received_at": utc(selection["revision"]["received_at"])}
        _, old_text = read_packet(revision, selection["packet_sha256"], root=state["articles"])
        saved = capture(revision, client, root=state["articles"])
        packet, new_text = read_packet(revision, saved["packet_sha256"], root=state["articles"])
        selection["packet_sha256"] = saved["packet_sha256"]
        selection["body_review"] = {"start": None, "end": None, "complete_body": False,
                                    "reviewer_id": "", "boundary_basis": "", "reviewed_at": None}
        receipt = {"schema": "ARTICLE_REVIEW_V1", "entry_sha256": digest(entry),
                   "anchors": pinned, "selection_sha256": digest({k: v for k, v in selection.items()
                                                                    if k != "body_review"}),
                   "prepared_at": packet["retrieved_at"], "delivery": "disabled"}
        output.mkdir(parents=True, exist_ok=False)
        for name, value in (("receipt", receipt), ("selection", selection)):
            (output / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "candidate.txt").write_text(new_text, encoding="utf-8")
        diff = "\n".join(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(),
                                              fromfile="previous", tofile="candidate", lineterm=""))
        (output / "review.html").write_text('<!doctype html><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'">'
            '<title>Local article replacement review</title><h1>Unapproved candidate</h1>'
            '<p>Review complete body offsets in candidate.txt. No financial or causal approval.</p><pre>'
            + html.escape(diff or "No visible text change; explicit review still required.") + '</pre>', encoding="utf-8")
    return {"status": "DRAFT_REVIEW_REQUIRED", "delivery": "disabled"}


def approve(conn, folder, *, root=None):
    folder = Path(folder)
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    selection = json.loads((folder / "selection.json").read_text(encoding="utf-8"))
    if (receipt["schema"] != "ARTICLE_REVIEW_V1" or digest({k: v for k, v in selection.items()
            if k != "body_review"}) != receipt["selection_sha256"]):
        raise ValueError("Pinned candidate changed; prepare again")
    return approve_replacement(conn, selection, root=root,
        expected_entry=receipt["entry_sha256"], expected_anchors=receipt["anchors"])


def main():
    from engine.db import database
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["queue", "prepare", "approve"])
    parser.add_argument("--url")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    db = database()
    try:
        with db.connect() as conn:
            if args.action == "queue":
                result = queue(conn)
            elif args.output is None:
                parser.error("--output review directory required")
            elif args.action == "prepare":
                if not args.url:
                    parser.error("--url required")
                client = NewsClient()
                try:
                    result = prepare(conn, client, args.url, args.output)
                finally:
                    client.close()
            else:
                result = approve(conn, args.output)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        db.dispose()


if __name__ == "__main__":
    main()
