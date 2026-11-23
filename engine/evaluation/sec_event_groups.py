"""Conservative source-cited event grouping for an offline relevance challenge."""

import argparse
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from engine.evaluation.archived_profile_relevance import PARTY, SCOPE, freeze_selected
from engine.evaluation.archived_profile_relevance import evaluate as evaluate_archive
from engine.evaluation.held_role_corpus import read
from engine.evaluation.profile_relevance import overlaps, shingles, write_new
from engine.evaluation.prospective import Paragraphs
from engine.evaluation.sec_family_capture import exact_capture, family_url
from engine.ingestion.contracts import digest
from engine.sec_review import plain_text


def cited_date(documents, value, earnings):
    day = date.fromisoformat(value)
    patterns = [re.escape(day.strftime("%B")) + r"\s+0?" + str(day.day)
                + r",?\s+" + str(day.year), re.escape(value)]
    for document, text, _ in documents:
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                before = text[max(0, match.start() - 110):match.start()]
                if earnings and not re.search(r"(?:quarter|year|period).*ended\s*$", before, re.I):
                    continue
                return {"url": document["url"], "text_sha256": document["text_sha256"],
                        "start": match.start(), "end": match.end(), "quote": match.group(),
                        "context": text[max(0, match.start() - 110):match.end() + 70]}
    return None


def event_key(family, reviews, documents):
    """Earnings use cited economic periods; other events retain accession identity."""
    periods = [set(re.findall(r"ended (\d{4}-\d{2}-\d{2})",
                             str(r["economic_period_or_event_date"]))) for r in reviews]
    earnings = (any(periods) or any(re.search(r"earnings|financial.results|results.of.operations",
                    str(r.get("event_kind", "")), re.I) for r in reviews)
                or any(re.search(r"Item\s+2\.02\b", text, re.I)
                       for doc, text, _ in documents if doc["role"] == "primary"))
    if earnings and (len(periods[0]) != 1 or periods[0] != periods[1]):
        return None
    value = next(iter(periods[0])) if earnings else family["report_period"]
    citation = cited_date(documents, value, earnings)
    if not citation:
        return None
    if date.fromisoformat(value) > date.fromisoformat(family["filing_date"]):
        return None
    key = (f"{family['cik']}:EARNINGS:{value}" if earnings else
           f"{family['cik']}:EVENT:{value}:{family['id']}")
    return {"key": key, "kind": "EARNINGS" if earnings else "ACCESSION_EVENT",
            "date": value, "citation": citation}


def load_reviewed(packet_root, review_paths):
    packet, receipt = read(packet_root / "packet.json"), read(packet_root / "receipt.json")
    if digest(packet) != receipt["packet_sha256"]:
        raise ValueError("Source packet changed")
    ids = {r["id"] for r in packet}
    if len(ids) != len(packet) or len(review_paths) != 2:
        raise ValueError("Unique families and two reviews required")
    reviews, reviewer_ids = [], set()
    for path in review_paths:
        review = read(path)
        at = datetime.fromisoformat(review["reviewed_at"])
        if (review["packet_sha256"] != digest(packet)
                or review["reviewer_kind"] != "AI_INDEPENDENT"
                or review["peer_reviews_accessed"] is not False
                or not review["reviewer_id"] or review["reviewer_id"] in reviewer_ids
                or at.tzinfo is None or at > datetime.now(UTC)):
            raise ValueError("Invalid independent source review")
        if len(review["families"]) != len(ids) or {r["id"] for r in review["families"]} != ids:
            raise ValueError("Incomplete source review")
        reviewer_ids.add(review["reviewer_id"])
        reviews.append({r["id"]: r for r in review["families"]})
    validated = []
    for family in packet:
        documents = []
        if sum(d["role"] == "primary" for d in family["documents"]) != 1:
            raise ValueError("Exactly one primary required")
        for doc in family["documents"]:
            if not family_url({"cik": family["cik"], "accession": family["id"]}, doc["url"]):
                raise ValueError("Cross-family source")
            exact_capture(packet_root, doc["html"], doc["raw_sha256"])
            exact_capture(packet_root, doc["text"], doc["text_sha256"])
            raw = (packet_root / doc["html"]).read_text(encoding="utf-8")
            text = (packet_root / doc["text"]).read_text(encoding="utf-8")
            if plain_text(raw) != text:
                raise ValueError("Source text transformation changed")
            documents.append((doc, text, raw))
        validated.append((family, [r[family["id"]] for r in reviews], documents))
    return validated


def prepare(packet_root, review_paths, output, previous=()):
    if output.exists():
        raise ValueError("Frozen output exists")
    reviewed = load_reviewed(packet_root, review_paths)
    prior_periods, prior_keys, prior_hashes, prior_urls, prior_text = set(), set(), set(), set(), []
    for path in previous:
        old, receipt = read(path), read(path.with_name("freeze.json"))
        if digest(old) != receipt["packet_sha256"]:
            raise ValueError("Prior packet changed")
        for item in old:
            source = item.get("archive_source", {})
            if source.get("report_period"):
                prior_periods.add((source.get("ticker"), source["report_period"]))
            prior_keys.add(source.get("event_group_key"))
            prior_hashes.add(source.get("source_sha256"))
            prior_urls.add(source.get("url"))
            prior_text.append(shingles(item["article"]))
    selected, audit, seen_groups, seen_text = [], [], set(), list(prior_text)
    excluded_passages = 0
    for family, votes, documents in reviewed:
        grouping = event_key(family, votes, documents)
        reason = None
        if any(v["scoped_context_sufficient"] is not True for v in votes):
            reason = "SOURCE_REVIEW_INSUFFICIENT"
        elif any(v["missing_or_external_context"] for v in votes):
            reason = "EXTERNAL_CONTEXT_HELD"
        elif grouping is None:
            reason = "UNCERTAIN_EVENT_PERIOD"
        elif (grouping["key"] in prior_keys or (grouping["kind"] == "EARNINGS"
                and (family["ticker"], grouping["date"]) in prior_periods)):
            reason = "PREVIOUS_ECONOMIC_PERIOD"
        elif any(d["raw_sha256"] in prior_hashes or d["url"] in prior_urls for d, _, _ in documents):
            reason = "PREVIOUS_SOURCE_FAMILY"
        elif grouping["key"] in seen_groups:
            reason = "DUPLICATE_EVENT_GROUP"
        candidates = []
        if reason is None:
            for doc, _, raw in documents:
                parser = Paragraphs()
                parser.feed(raw)
                parser.flush()
                for i, text in enumerate(dict.fromkeys(parser.rows)):
                    if not 160 <= len(text) <= 1600:
                        continue
                    article = {"title": "", "summary": text}
                    if overlaps(shingles(article), seen_text):
                        excluded_passages += 1
                        continue
                    stratum = "named_party" if PARTY.search(text) else (
                        "identity_scope" if SCOPE.search(text) else "control")
                    candidates.append((stratum, doc, i, article))
            if not candidates:
                reason = "NO_UNUSED_PASSAGE"
        if reason is None:
            assert grouping is not None
            # Fixed vocabulary priority, independent of matching outcomes or labels.
            order = {"named_party": 0, "identity_scope": 1, "control": 2}
            stratum, doc, i, article = min(candidates, key=lambda c: order[c[0]])
            source = {"ticker": family["ticker"], "cik": family["cik"],
                "accession": family["id"], "filing_date": family["filing_date"],
                "report_period": grouping["date"] if grouping["kind"] == "EARNINGS" else None,
                "cluster_key": grouping["key"], "event_group_key": grouping["key"],
                "grouping_citation": grouping["citation"], "source_sha256": doc["raw_sha256"],
                "url": doc["url"], "form": "8-K_CONTEXT",
                "related_source_urls": [d["url"] for d, _, _ in documents],
                "available_at_basis": "CURRENT_CAPTURED_TEXT_ONLY_NOT_HISTORICAL_REPLAY"}
            selected.append({"source": source, "paragraph_index": i, "article": article,
                             "sampling_stratum": stratum})
            seen_groups.add(grouping["key"])
            seen_text.append(shingles(article))
        audit.append({"id": family["id"], "grouping": grouping,
                      "status": reason or "SELECTED_TEXT_ONLY"})
    counts = dict(Counter(r["status"] for r in audit))
    report = {"families": len(reviewed), "disposition": counts, "selected": len(selected),
              "delivery": "disabled", "ingested": False}
    if not selected:
        output.mkdir(parents=True)
        write_new(output / "grouping.json", audit)
        write_new(output / "readiness.json", report)
        return report
    result = freeze_selected(selected, output, len(reviewed), excluded_passages,
        digest(read(packet_root / "packet.json")), previous, extra_receipt={
            "event_grouping_sha256": digest(audit), "grouping_report": report,
            "source_review_sha256": [digest(read(p)) for p in review_paths],
            "sampling": "ONE_PER_CITED_EVENT_GROUP_FIXED_PARTY_SCOPE_CONTROL_PRIORITY",
            "limitations": ["Source-reviewed documents are exposed, not a pristine holdout",
                "Current profiles and present captures, not point-in-time replay",
                "External-context families withheld, not negative labels",
                "Prior issuer-period/source/text exclusions cover supplied packets only",
                "Non-earnings accessions remain separate; semantic cross-accession dedup incomplete",
                "Relevance only, not financial impact, source truth or production approval"]})
    write_new(output / "grouping.json", audit)
    return result


def evaluate(output, labels):
    frozen = read(output / "freeze.json")
    if digest(read(output / "grouping.json")) != frozen.get("event_grouping_sha256"):
        raise ValueError("Event grouping changed")
    return evaluate_archive(output, labels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-root", type=Path, required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-packet", type=Path, action="append", default=[])
    args = parser.parse_args()
    import json
    print(json.dumps(prepare(args.packet_root, args.review, args.output, args.exclude_packet), indent=2))
