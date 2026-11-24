"""Freeze exact, independently scoped excerpts without approving their whole filing."""

import hashlib
from datetime import UTC, datetime

from engine.evaluation.archived_profile_relevance import freeze_selected
from engine.evaluation.held_role_corpus import read
from engine.evaluation.profile_relevance import overlaps, shingles, write_new
from engine.evaluation.sec_event_groups import cited_date
from engine.evaluation.sec_family_capture import exact_capture, family_url
from engine.ingestion.contracts import digest
from engine.sec_review import plain_text


def approved_rows(directory, source_root, review_paths):
    packet = read(directory / "packet.json")
    sha = digest(packet)
    if sha != read(directory / "receipt.json")["packet_sha256"] or len(review_paths) != 2:
        raise ValueError("Scope packet or review count invalid")
    originals = read(source_root / "packet.json")
    if digest(originals) != read(source_root / "receipt.json")["packet_sha256"]:
        raise ValueError("Original source packet changed")
    originals = {r["id"]: r for r in originals}
    ids = {r["id"] for r in packet}
    if len(ids) != len(packet):
        raise ValueError("Repeated scope candidate")
    votes, actors = [], set()
    for path in review_paths:
        review = read(path)
        at = datetime.fromisoformat(review["reviewed_at"])
        if (review["packet_sha256"] != sha or review["reviewer_kind"] != "AI_INDEPENDENT"
                or review["peer_reviews_accessed"] is not False or not review["reviewer_id"]
                or review["reviewer_id"] in actors or at.tzinfo is None or at > datetime.now(UTC)):
            raise ValueError("Invalid source scope reviewer")
        if len(review["passages"]) != len(ids) or {r["id"] for r in review["passages"]} != ids:
            raise ValueError("Incomplete scope review")
        actors.add(review["reviewer_id"])
        votes.append({r["id"]: r for r in review["passages"]})
    selected, withheld = [], []
    for row in packet:
        family = originals.get(row["id"])
        if family != row["family"] or row["document"] not in family["documents"]:
            raise ValueError("Candidate source identity changed")
        docs = []
        for doc in family["documents"]:
            if not family_url({"cik": family["cik"], "accession": family["id"]}, doc["url"]):
                raise ValueError("Cross-family source")
            exact_capture(source_root, doc["html"], doc["raw_sha256"])
            exact_capture(source_root, doc["text"], doc["text_sha256"])
            raw = (source_root / doc["html"]).read_text(encoding="utf-8")
            text = (source_root / doc["text"]).read_text(encoding="utf-8")
            if plain_text(raw) != text:
                raise ValueError("Source transform changed")
            docs.append((doc, text, raw))
        text = next(t for d, t, _ in docs if d == row["document"])
        start, end = row["text_start"], row["text_end"]
        if not 0 <= start < end <= len(text) or text[start:end] != row["quote"]:
            raise ValueError("Exact scoped passage changed")
        pair = [v[row["id"]] for v in votes]
        quote_sha = hashlib.sha256(row["quote"].encode()).hexdigest()
        if any(v["quote_sha256"] != quote_sha for v in pair):
            raise ValueError("Review quote hash changed")
        period = pair[0]["economic_period"]
        citation = cited_date(docs, period, True)
        if (any(v["approved"] is not True or v["external_context_required"] is not False
                or v["scope"] != "EXACT_PASSAGE_INFORMATIONAL_ONLY" for v in pair)
                or period != pair[1]["economic_period"] or not citation):
            withheld.append(row["id"])
            continue
        selected.append({**row, "period": period, "period_citation": citation,
                         "limitations": list(dict.fromkeys(x for v in pair for x in v["limitations"]))})
    return selected, withheld


def freeze(directory, source_root, reviews, output, previous=()):
    if output.exists():
        raise ValueError("Frozen output exists")
    rows, held = approved_rows(directory, source_root, reviews)
    periods, hashes, texts = set(), set(), []
    for path in previous:
        packet = read(path)
        if digest(packet) != read(path.with_name("freeze.json"))["packet_sha256"]:
            raise ValueError("Prior packet changed")
        for row in packet:
            source = row.get("archive_source", {})
            periods.add((source.get("ticker"), source.get("report_period")))
            hashes.add(source.get("source_sha256"))
            texts.append(shingles(row["article"]))
    selected, excluded = [], 0
    for row in rows:
        family, doc = row["family"], row["document"]
        article = {"title": "", "summary": row["quote"]}
        key = (family["ticker"], row["period"])
        if key in periods or doc["raw_sha256"] in hashes or overlaps(shingles(article), texts):
            excluded += 1
            continue
        source = {"ticker": family["ticker"], "cik": family["cik"], "accession": family["id"],
            "filing_date": family["filing_date"], "report_period": row["period"],
            "cluster_key": family["cik"] + ":EARNINGS:" + row["period"],
            "url": doc["url"], "source_sha256": doc["raw_sha256"],
            "source_text_span": {"start": row["text_start"], "end": row["text_end"]},
            "scope": "EXACT_PASSAGE_INFORMATIONAL_ONLY", "scope_limitations": row["limitations"],
            "whole_filing_verified": False, "period_citation": row["period_citation"]}
        selected.append({"source": source, "article": article,
                         "paragraph_index": row["paragraph_index"], "sampling_stratum": "scoped_text"})
        periods.add(key)
        texts.append(shingles(article))
    report = {"candidates": len(rows) + len(held), "scope_held": len(held),
              "previously_exposed": excluded, "selected": len(selected), "delivery": "disabled"}
    if not selected:
        output.mkdir(parents=True)
        write_new(output / "readiness.json", report)
        return report
    return freeze_selected(selected, output, len(rows) + len(held), excluded,
        digest(read(directory / "packet.json")), previous, extra_receipt={
            "scope_review_sha256": [digest(read(p)) for p in reviews], "scope_report": report,
            "sampling": "FIRST_UNQUOTED_OWN_ISSUER_OPERATING_PARAGRAPH_FIXED_TERMS",
            "limitations": ["Independent exact-passage scope only; whole source remains incomplete",
                "Source auditors saw documents; relevance labelers must use new contexts",
                "Present profiles and captures, not point-in-time replay or human gold",
                "Own-issuer unquoted-text convenience sample, not whole-market accuracy"]})
