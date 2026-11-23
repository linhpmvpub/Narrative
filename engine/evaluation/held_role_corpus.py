"""Validate held SEC captures and freeze complete periodic documents only, offline."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from engine.collect_sec import candidates, identities
from engine.evaluation.archived_profile_relevance import (
    PARTY,
    SCOPE,
    freeze_selected,
)
from engine.evaluation.archived_profile_relevance import (
    evaluate as evaluate_archive,
)
from engine.evaluation.profile_relevance import overlaps, shingles, write_new
from engine.evaluation.prospective import Paragraphs
from engine.ingestion.contracts import digest


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checked(root, name, expected):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Capture escapes root")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        # Legacy Windows collector persisted SourceClient text with CRLF translation.
        # Accept only this reversible storage transform; seal physical bytes separately.
        raw = raw.replace(b"\r\n", b"\n")
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Capture hash mismatch")
    return raw.decode("utf-8")


class Links(HTMLParser):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.links: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        link = urlsplit(urljoin(self.url, href))
        base = urlsplit(self.url)
        if (link.scheme == "https" and link.netloc == base.netloc
                and link.path.startswith(base.path.rsplit("/", 1)[0] + "/")
                and link.path != base.path and link.path.lower().endswith((".htm", ".html"))):
            self.links.add(link._replace(query="", fragment="").geturl())


def audit(index, metadata, root, now=None):
    """Cross-check every filing with hashed SEC identity/submission snapshots."""
    now = now or datetime.now(UTC)
    held = read(index)
    manifest = read(metadata / "collection.json")
    issuer_map = identities(json.loads(checked(metadata, "company_tickers.json",
                                               manifest["index_sha256"])))
    output, seen_url, seen_hash = [], set(), set()
    for filing in held["filings"]:
        ticker = filing["ticker"]
        identity = manifest["identities"][ticker]
        if identity["cik"] != issuer_map[ticker]["cik"] or filing["cik"] != identity["cik"]:
            raise ValueError("Issuer identity mismatch")
        payload = json.loads(checked(metadata, ticker + "-submissions.json",
                                     identity["submission_sha256"]))
        rows = candidates(ticker, identity["cik"], payload, date.min, now.date(), 10000)
        if not any(all(filing[k] == r[k] for k in
                       ("url", "cik", "accession", "form", "filing_date")) for r in rows):
            raise ValueError("Filing not in captured SEC submissions")
        recent = payload["filings"]["recent"]
        if len(recent["reportDate"]) != len(recent["accessionNumber"]):
            raise ValueError("Invalid report-period column")
        i = recent["accessionNumber"].index(filing["accession"])
        period = recent["reportDate"][i]
        if period:
            date.fromisoformat(period)
        acquired = datetime.fromisoformat(filing["retrieved_at"])
        first = datetime.fromisoformat(filing["first_available_to_engine_at"])
        if (acquired.tzinfo is None or first.tzinfo is None or not acquired <= first <= now
                or acquired.date() < date.fromisoformat(filing["filing_date"])):
            raise ValueError("Invalid source availability clock")
        directory = (root / filing["collection_directory"]).resolve()
        if not directory.is_relative_to(root.resolve()):
            raise ValueError("Collection escapes root")
        raw = checked(directory, filing["file"], filing["content_sha256"])
        links = Links(filing["url"])
        links.feed(raw)
        family = filing["form"].removesuffix("/A")
        amendments = [r["accession"] for r in rows if r["form"] == family + "/A"
                      and recent["reportDate"][recent["accessionNumber"].index(r["accession"])]
                      == period]
        reason = None
        if not period:
            reason = "MISSING_REPORT_PERIOD"
        elif family == "8-K":
            reason = "EVENT_AND_EXHIBIT_REVIEW_REQUIRED"
        elif amendments or filing["form"].endswith("/A"):
            reason = "AMENDMENT_FAMILY_REVIEW_REQUIRED"
        elif filing["url"] in seen_url or filing["content_sha256"] in seen_hash:
            reason = "DUPLICATE_DOCUMENT"
        seen_url.add(filing["url"])
        seen_hash.add(filing["content_sha256"])
        output.append({"source": {**filing, "source_sha256": filing["content_sha256"],
                       "stored_bytes_sha256": hashlib.sha256((directory / filing["file"]).read_bytes()).hexdigest(),
                       "report_period": period, "cluster_key": filing["cik"] + ":" + period,
                       "known_amendments": amendments},
                       "status": reason or "ELIGIBLE_TEXT_CHALLENGE_ONLY",
                       "linked_documents": sorted(links.links), "raw": raw})
    return output


def prepare(index, metadata, root, output, exclude_packets=(), count=24):
    if not 1 <= count <= 100:
        raise ValueError("Choose 1..100 clusters")
    if output.exists():
        raise ValueError("Output exists; frozen runs must not be overwritten")
    rows = audit(index, metadata, root)
    prior, excluded_docs = [], set()
    for path in exclude_packets:
        packet, receipt = read(path), read(path.with_name("freeze.json"))
        if digest(packet) != receipt["packet_sha256"]:
            raise ValueError("Excluded packet changed")
        for item in packet:
            prior.append(shingles(item["article"]))
            excluded_docs.add(item.get("archive_source", {}).get("source_sha256"))
    buckets: dict[str, list] = {"named_party": [], "identity_scope": [], "control": []}
    excluded_passages = 0
    for row in rows:
        source = row["source"]
        if source["source_sha256"] in excluded_docs:
            row["status"] = "PREVIOUSLY_REVIEWED_DOCUMENT"
        if row["status"] != "ELIGIBLE_TEXT_CHALLENGE_ONLY":
            continue
        parser = Paragraphs()
        parser.feed(row["raw"])
        parser.flush()
        for i, text in enumerate(dict.fromkeys(parser.rows)):
            if not 160 <= len(text) <= 1600:
                continue
            article = {"title": "", "summary": text}
            if overlaps(shingles(article), prior):
                excluded_passages += 1
                continue
            group = "named_party" if PARTY.search(text) else (
                "identity_scope" if SCOPE.search(text) else "control")
            buckets[group].append({"source": source, "article": article,
                                   "paragraph_index": i, "sampling_stratum": group})
    selected: list = []
    clusters: set[str] = set()
    seen = list(prior)
    while any(buckets.values()) and len(selected) < count:
        for bucket in buckets.values():
            while bucket and len(selected) < count:
                row = bucket.pop(0)
                fingerprint = shingles(row["article"])
                if row["source"]["cluster_key"] in clusters or overlaps(fingerprint, seen):
                    continue
                selected.append(row)
                clusters.add(row["source"]["cluster_key"])
                seen.append(fingerprint)
                break
    report = {"documents": len(rows), "disposition": dict(Counter(r["status"] for r in rows)),
              "linked_document_candidates": sum(len(r["linked_documents"]) for r in rows),
              "selected_clusters": len(selected), "requested_clusters": count,
              "delivery": "disabled", "ingested": False}
    audit_rows = [{k: v for k, v in r.items() if k != "raw"} for r in rows]
    if not selected:
        output.mkdir(parents=True)
        write_new(output / "source-audit.json", audit_rows)
        write_new(output / "readiness.json", report)
        return report
    frozen = freeze_selected(selected, output, count, excluded_passages, digest(read(index)), exclude_packets,
        document_previously_exposed=False, extra_receipt={
            "source_audit_sha256": digest(audit_rows), "held_corpus": report,
            "metadata_manifest_sha256": digest(read(metadata / "collection.json")),
            "limitations": ["Current profiles applied to captured text, not point-in-time replay",
                "New only against supplied prior packets; not proof of pretraining independence",
                "8-K event/exhibit and amendment families withheld, not negative examples",
                "Strata are vocabulary samples, not positive/negative labels; underfill explicit",
                "Relevance only; no ingestion, financial impact or notification evaluation"]})
    write_new(output / "source-audit.json", audit_rows)
    write_new(output / "readiness.json", report)
    return frozen


def evaluate(output, labels):
    frozen = read(output / "freeze.json")
    if digest(read(output / "source-audit.json")) != frozen.get("source_audit_sha256"):
        raise ValueError("Source audit changed")
    return evaluate_archive(output, labels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-packet", type=Path, action="append", default=[])
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()
    print(json.dumps(prepare(args.index, args.metadata, args.root, args.output,
                             args.exclude_packet, args.count), indent=2))
