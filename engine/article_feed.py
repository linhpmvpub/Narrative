"""Opt-in local full-article research feed with fail-closed source revalidation."""
import argparse
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from engine.adapters.news import FetchError, NewsClient, canonical_url
from engine.article_cards import build
from engine.company_profiles import writer_lock
from engine.evaluation.article_relevance import reviewed_body, utc
from engine.ingestion.contracts import digest
from engine.models.schema_v13 import news_items, news_sources
from engine.news_articles import capture, read_packet

WITHDRAWAL = re.compile(r"\bthis (?:story|article|report|press release) (?:has been|was|is) "
                        r"(?:retracted|withdrawn)\b", re.I)


class SourceWithdrawn(ValueError):
    pass


def root_dir():
    return Path(os.getenv("ARTICLE_FEED_ROOT", "source-cache/article-feed"))


def write_state(root, state):
    state["version"] += 1
    temporary = root / "current.tmp"
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    with (root / f'state-v{state["version"]}.json').open("x", encoding="utf-8") as stream:
        stream.write(temporary.read_text(encoding="utf-8"))
    temporary.replace(root / "current.json")


def anchors(conn, url):
    rows = conn.execute(select(news_items, news_sources.c.config.label("source_config")).join(
        news_sources, news_sources.c.id == news_items.c.source_id).where(
        news_items.c.article_key == digest(canonical_url(url)))).mappings().all()
    result = []
    for row in rows:
        payload = row["payload"]
        if (payload.get("withdrawn") or payload.get("status") in {"WITHDRAWN", "RETRACTED"}
                or WITHDRAWAL.search(payload.get("title", "") + " " + payload.get("summary", ""))):
            raise SourceWithdrawn("Publisher withdrawal")
        if not row["source_config"].get("enabled") or digest(payload) != row["content_sha256"]:
            raise ValueError("Inbox source disabled, withdrawn or corrupt")
        result.append({"id": row["id"], "version": row["version"], "sha256": row["content_sha256"]})
    return sorted(result, key=lambda r: r["id"])


def install(conn, selections, profiles, articles, *, root=None):
    root = Path(root) if root is not None else root_dir()
    if not 1 <= len(selections) <= 100:
        raise ValueError("Choose 1..100 reviewed selections")
    now = datetime.now(UTC)
    entries, seen = [], set()
    for selection in selections:
        reviewed_body(selection, now, article_root=articles)
        url = selection["revision"]["payload"]["url"]
        key = canonical_url(url)
        if key in seen:
            raise ValueError("Duplicate article URL")
        seen.add(key)
        entries.append({"selection": selection, "status": "AWAITING_RECHECK",
                        "anchors": anchors(conn, url), "checked_at": None, "proof": None})
    root.mkdir(parents=True, exist_ok=True)
    with writer_lock(root):
        if (root / "current.json").exists():
            raise ValueError("Install in a new root; preserve previous review versions")
        state = {"schema": "ARTICLE_FEED_V1", "version": 0, "entries": entries,
                 "profiles": str(Path(profiles).resolve()), "articles": str(Path(articles).resolve())}
        write_state(root, state)
    return {"articles": len(entries), "delivery": "disabled"}


def refresh(conn, client, *, root=None):
    root = Path(root) if root is not None else root_dir()
    with writer_lock(root):
        state = json.loads((root / "current.json").read_text(encoding="utf-8"))
        # Invalidate before network work; crashes cannot leave stale active cards.
        for entry in state["entries"]:
            if entry["status"] not in {"REVIEW_REQUIRED", "WITHDRAWN"}:
                entry["status"] = "CHECKING"
        write_state(root, state)
        for entry in state["entries"]:
            if entry["status"] in {"REVIEW_REQUIRED", "WITHDRAWN"}:
                continue  # Never revive a changed/retracted article without a new reviewed install.
            selection = entry["selection"]
            rev = {**selection["revision"], "received_at": utc(selection["revision"]["received_at"])}
            try:
                if anchors(conn, rev["payload"]["url"]) != entry["anchors"]:
                    entry["status"] = "REVIEW_REQUIRED"
                    continue
                old, _ = reviewed_body(selection, datetime.now(UTC), article_root=state["articles"])
                saved = capture(rev, client, root=state["articles"])
                packet, text = read_packet(rev, saved["packet_sha256"], root=state["articles"])
                entry["proof"] = saved["packet_sha256"]
                entry["checked_at"] = packet["retrieved_at"]
                entry["status"] = ("WITHDRAWN" if WITHDRAWAL.search(text) else
                    "ACTIVE" if packet["text_sha256"] == old["text_sha256"] else "REVIEW_REQUIRED")
            except SourceWithdrawn:
                entry["status"] = "WITHDRAWN"
            except (OSError, ValueError, KeyError, TypeError, FetchError):
                entry["status"] = "UNAVAILABLE"
        write_state(root, state)
    return {"states": {s: sum(e["status"] == s for e in state["entries"])
                       for s in sorted({e["status"] for e in state["entries"]})}, "delivery": "disabled"}


def approve_replacement(conn, selection, *, root=None, expected_entry=None, expected_anchors=None):
    """Explicit local operator review; a refresh can never perform this transition."""
    root = Path(root) if root is not None else root_dir()
    with writer_lock(root):
        state = json.loads((root / "current.json").read_text(encoding="utf-8"))
        reviewed_body(selection, datetime.now(UTC), article_root=state["articles"])
        url = selection["revision"]["payload"]["url"]
        entry = next((e for e in state["entries"] if canonical_url(
            e["selection"]["revision"]["payload"]["url"]) == canonical_url(url)), None)
        if entry is None:
            raise ValueError("Replacement must identify an existing article")
        if expected_entry is not None and digest(entry) != expected_entry:
            raise ValueError("Review is stale; prepare a new review packet")
        current_anchors = anchors(conn, url)
        if expected_anchors is not None and current_anchors != expected_anchors:
            raise ValueError("Inbox changed during review; prepare again")
        old = entry["selection"]
        cutoff = max(utc(old["body_review"]["reviewed_at"]),
                     utc(entry["checked_at"] or old["body_review"]["reviewed_at"]))
        if (selection["packet_sha256"] == old["packet_sha256"]
                or utc(selection["body_review"]["reviewed_at"]) <= cutoff):
            raise ValueError("New capture and later explicit body review required")
        entry.update(selection=selection, anchors=current_anchors,
                     status="AWAITING_RECHECK", checked_at=None, proof=None)
        write_state(root, state)
    return {"status": "AWAITING_RECHECK", "version": state["version"], "delivery": "disabled"}


def feed(conn, *, root=None, ticker=None, narrative=None):
    root = Path(root) if root is not None else root_dir()
    empty: dict = {"items": [], "delivery": "disabled", "mode": "RESEARCH_FULL_ARTICLE_FEED"}
    try:
        raw = (root / "current.json").read_bytes()
        state = json.loads(raw)
        if state["schema"] != "ARTICLE_FEED_V1" or not 1 <= len(state["entries"]) <= 100:
            raise ValueError("Invalid bounded manifest")
        now = datetime.now(UTC)
        selections = []
        for entry in state["entries"]:
            if entry["status"] != "ACTIVE":
                continue
            try:
                if not now - timedelta(hours=1) <= utc(entry["checked_at"]) <= now:
                    continue
                selection = entry["selection"]
                rev = {**selection["revision"], "received_at": utc(selection["revision"]["received_at"])}
                if anchors(conn, rev["payload"]["url"]) != entry["anchors"]:
                    continue
                old, _ = reviewed_body(selection, now, article_root=state["articles"])
                proof, text = read_packet(rev, entry["proof"], root=state["articles"])
                if (proof["text_sha256"] != old["text_sha256"] or WITHDRAWAL.search(text)
                        or proof["retrieved_at"] != entry["checked_at"]):
                    continue
                selections.append(selection)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        result = build(selections, now, profile_root=state["profiles"], article_root=state["articles"]) if selections else empty
        if (root / "current.json").read_bytes() != raw:
            raise ValueError("Source revalidation changed during projection")
        cards = [c for c in result["items"] if (not ticker or c["ticker"] == ticker)
                 and (not narrative or c["profile_id"] + ":" + c["narrative_id"] == narrative)]
        return {**empty, "items": cards, "enabled": True, "version": state["version"],
                "held_articles": len(state["entries"]) - len(selections),
                "checked_articles": len(selections), "recheck_ttl_seconds": 3600}
    except FileNotFoundError:
        return {**empty, "enabled": False}
    except (OSError, ValueError, KeyError, TypeError):
        return {**empty, "enabled": True, "withheld": True}


def main():
    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "refresh", "approve-replacement"])
    parser.add_argument("--selections", type=Path)
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--articles", type=Path)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval", type=int, default=900)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 1440 or not 60 <= args.interval <= 3600:
        parser.error("Bounded cycles and interval required")
    db, client = database(), NewsClient()
    try:
        with db.connect() as conn:
            if args.action == "approve-replacement":
                if not args.selections:
                    parser.error("Replacement requires one reviewed selection")
                selections = json.loads(args.selections.read_text(encoding="utf-8"))
                if not isinstance(selections, list) or len(selections) != 1:
                    parser.error("Replacement requires exactly one reviewed selection")
                print(json.dumps(approve_replacement(conn, selections[0])))
            elif args.action == "install":
                if not all([args.selections, args.profiles, args.articles]):
                    parser.error("Install requires selections, profiles and articles")
                print(json.dumps(install(conn, json.loads(args.selections.read_text(encoding="utf-8")),
                                         args.profiles, args.articles)))
            else:
                for i in range(args.cycles):
                    print(json.dumps(refresh(conn, client)), flush=True)
                    conn.rollback()  # New DB snapshot on the next cycle.
                    if i + 1 < args.cycles:
                        time.sleep(args.interval)
    finally:
        client.close()
        db.dispose()


if __name__ == "__main__":
    main()
