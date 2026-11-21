"""Conservative Inline XBRL segments and issuer attribution, never causal approval."""

import hashlib
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from engine.development_feed import require_enabled
from engine.financials import METRICS, extract, known_filings, source_identity
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v9 import filing_evidence_snapshots as snapshots

XBRL = "http://www.xbrl.org/2003/instance"
IX = "http://www.xbrl.org/2013/inlineXBRL"
XD = "http://xbrl.org/2006/xbrldi"
AXIS = "us-gaap:StatementBusinessSegmentsAxis"
CAUSAL = re.compile(r"\b(driven by|due to|attributable to|resulted from|reflecting)\b", re.I)
OUTCOME = re.compile(r"\b(revenue|margin|income|profit|sales)\b", re.I)
UNCERTAIN = re.compile(r"\b(may|could|might|expect|expects|would|will|risk|not|unlikely)\b", re.I)
RELATION_SCREEN: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "MU": [
        ("R005", (r"\bDRAM\b", r"selling prices?", r"gross margin")),
        ("R006", (r"\bDRAM\b", r"selling prices?", r"revenue")),
    ],
    "AMD": [
        ("R019", (r"\bEPYC\b", r"data center", r"revenue")),
        ("R017", (r"\bInstinct\b", r"data center", r"revenue")),
    ],
    "NVDA": [("R010", (r"data center", r"demand", r"revenue"))],
    "DELL": [
        ("R024", (r"AI.optimized", r"\bISG\b", r"margin")),
        ("R028", (r"pricing", r"\bISG\b", r"margin")),
    ],
    "SNDK": [("R032", (r"selling prices?", r"gross margin"))],
}


def text(node):
    return " ".join("".join(node.itertext()).split())


def number(node):
    """Accept only supported SEC numeric transformations; never guess locale/unit."""
    if node.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in {"true", "1"}:
        raise ValueError("Nil")
    fmt = node.get("format", "").split(":")[-1]
    if fmt not in {"", "num-dot-decimal", "numdotdecimal", "num-zero", "zerodash"}:
        raise ValueError("Unsupported transformation")
    raw = text(node)
    if fmt in {"num-zero", "zerodash"}:
        if raw not in {"—", "–", "-"}:
            raise ValueError("Invalid zero")
        raw = "0"
    if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", raw):
        raise ValueError("Unsupported number")
    scale = int(node.get("scale", "0"))
    if not -12 <= scale <= 12 or node.get("sign", "") not in {"", "-"}:
        raise ValueError("Invalid scale/sign")
    value = Decimal(raw.replace(",", "")) * (Decimal(10) ** scale)
    return -value if node.get("sign") == "-" else value


def parse(document, claim):
    if len(document.encode()) > 5_000_000 or re.search(r"<!\s*(DOCTYPE|ENTITY)", document, re.I):
        raise ValueError("Unsafe/oversized XML")
    root = ET.fromstring(document)
    contexts, units = {}, {}
    ids = [n.get("id") for n in root.iter() if n.get("id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Ambiguous duplicate XML IDs")
    for node in root.iter(f"{{{XBRL}}}unit"):
        measures = list(node.iter(f"{{{XBRL}}}measure"))
        if len(measures) == 1 and measures[0].text == "iso4217:USD":
            units[node.get("id")] = "USD"
    for node in root.iter(f"{{{XBRL}}}context"):
        ident = node.find(f".//{{{XBRL}}}identifier")
        if ident is None or ident.get("scheme") != "http://www.sec.gov/CIK":
            continue
        if int(ident.text or "-1") != int(claim["cik"]):
            continue
        if list(node.iter(f"{{{XD}}}typedMember")):
            continue
        dims = sorted((n.get("dimension"), text(n)) for n in node.iter(f"{{{XD}}}explicitMember"))
        # Reportable segments only, not product/geography/combined subgroup totals.
        segments = [member for axis, member in dims if axis == AXIS]
        if len(segments) != 1 or any(
            axis != AXIS
            and (axis, member) != ("srt:ConsolidationItemsAxis", "us-gaap:OperatingSegmentsMember")
            for axis, member in dims
        ):
            continue
        start = node.findtext(f".//{{{XBRL}}}startDate")
        end = node.findtext(f".//{{{XBRL}}}endDate")
        if start and end:
            contexts[node.get("id")] = (start, end, segments[0], dims)
    groups: dict = defaultdict(lambda: defaultdict(list))
    locators: dict = defaultdict(lambda: defaultdict(list))
    tags = {tag for _, choices in METRICS.values() for tag in choices}
    for node in root.iter(f"{{{IX}}}nonFraction"):
        concept = node.get("name", "")
        context = contexts.get(node.get("contextRef"))
        if not context or concept not in {"us-gaap:" + tag for tag in tags}:
            continue
        if node.get("unitRef") not in units or not node.get("id"):
            continue
        try:
            value = number(node)
        except (ValueError, InvalidOperation):
            continue
        start, end, segment, dims = context
        key = (segment, tuple(dims))
        tag = concept.split(":")[1]
        groups[key][tag].append(
            {
                "val": str(value),
                "start": start,
                "end": end,
                "form": claim["form"],
                "filed": claim["filing_date"],
                "accn": claim["accession"],
            }
        )
        locators[key][tag].append(
            {
                "fact_id": node.get("id"),
                "context_id": node.get("contextRef"),
                "scale": node.get("scale", "0"),
                "decimals": node.get("decimals"),
            }
        )
    comparisons = []
    for key, facts in groups.items():
        payload = {
            "facts": {"us-gaap": {tag: {"units": {"USD": rows}} for tag, rows in facts.items()}}
        }
        for item in extract(payload, claim["ticker"], {claim["accession"]: claim}):
            item.update(scope="reported_segment", segment=key[0], dimensions=[list(pair) for pair in key[1]])
            item["label"] = key[0].split(":")[-1].removesuffix("Member") + " · " + item["metric"]
            for operand in ("current", "prior"):
                pointer = item[operand].pop("json_pointer")
                index = int(pointer.rsplit("/", 1)[-1])
                item[operand].update(locators[key][item["concept"].split(":")[1]][index])
            comparisons.append(item)
    # Leaf narrative blocks exclude hidden XBRL metadata and table aggregates.
    paragraphs = []
    for node in root.iter():
        if node.tag.split("}")[-1] not in {"p", "div"}:
            continue
        if any(
            child.tag.split("}")[-1] in {"div", "p", "table"}
            for child in node.iter()
            if child is not node
        ):
            continue
        value = text(node)
        if 40 <= len(value) <= 3000 and OUTCOME.search(value):
            paragraphs.append(value)
    paragraphs = list(dict.fromkeys(paragraphs))
    attribution = []
    for index, value in enumerate(paragraphs):
        if CAUSAL.search(value):
            attribution.append(
                {
                    "id": digest([claim["accession"], value]),
                    "text": value,
                    "paragraph_index": index,
                    "paragraph_sha256": hashlib.sha256(value.encode()).hexdigest(),
                    "status": "UNCERTAIN_OR_FORWARD_LOOKING"
                    if UNCERTAIN.search(value)
                    else "ISSUER_ATTRIBUTION",
                    "source_span_verified": True,
                    "independently_verified": False,
                    "graph_eligible": False,
                    "candidate_relation_ids": [
                        rid
                        for rid, terms in RELATION_SCREEN.get(claim["ticker"], [])
                        if all(re.search(term, value, re.I) for term in terms)
                    ],
                    "relation_assessment": "LEXICAL_EVIDENCE_MATCH_ONLY; direction, mechanism and confounders require review",
                    "stock_price_impact": "UNKNOWN",
                    "limitations": [
                        "Issuer explanation is not independent causal identification",
                        "No estimated effect size or automatic graph approval",
                    ],
                }
            )
    return {
        "segments": comparisons,
        "attributions": attribution,
        "review_paragraphs": paragraphs,
        "method_version": "inline-segment-attribution-v1",
    }


def ingest(engine, claim, capture):
    require_enabled()
    now = datetime.now(UTC)
    expected = f"https://www.sec.gov/Archives/edgar/data/{int(claim['cik'])}/{claim['accession'].replace('-', '')}/"
    if capture.url != claim["url"] or not capture.url.startswith(expected):
        raise ValueError("Filing identity/URL mismatch")
    if (
        capture.retrieved_at.tzinfo is None
        or not datetime.combine(date.fromisoformat(claim["filing_date"]), datetime.min.time(), UTC)
        <= capture.retrieved_at
        <= now
    ):
        raise ValueError("Invalid capture time")
    if hashlib.sha256(capture.text.encode()).hexdigest() != capture.content_sha256:
        raise ValueError("Capture hash mismatch")
    payload = parse(capture.text, claim)
    payload["source_identity"] = source_identity(claim)
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        if conn.scalar(select(database_mode.c.mode).with_for_update()) != "production":
            raise ValueError("Non-synthetic source store required")
        current = known_filings(conn, claim["ticker"], now).get(claim["accession"])
        if (
            not current
            or source_identity(current) != source_identity(claim)
            or current.get("source_status", "active") != "active"
        ):
            raise ValueError("Canonical source changed or inactive")
        previous = (
            conn.execute(
                select(snapshots)
                .where(
                    snapshots.c.ticker == claim["ticker"],
                    snapshots.c.accession == claim["accession"],
                )
                .order_by(snapshots.c.version.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if previous and capture.retrieved_at < utc(previous["captured_at"]):
            raise ValueError("Stale capture")
        if (
            previous
            and previous["payload"] == payload
            and previous["capture_sha256"] == capture.content_sha256
        ):
            return {
                "status": "duplicate",
                "segments": len(payload["segments"]),
                "attributions": len(payload["attributions"]),
            }
        if previous and capture.retrieved_at <= utc(previous["captured_at"]):
            raise ValueError("Conflicting capture time")
        conn.execute(
            snapshots.insert().values(
                id=digest(
                    [
                        claim["ticker"],
                        claim["accession"],
                        capture.content_sha256,
                        capture.retrieved_at.isoformat(),
                    ]
                ),
                ticker=claim["ticker"],
                accession=claim["accession"],
                cik=claim["cik"],
                version=previous["version"] + 1 if previous else 1,
                capture_sha256=capture.content_sha256,
                source_url=capture.url,
                captured_at=capture.retrieved_at,
                available_at=now,
                payload=payload,
            )
        )
    return {
        "status": "created",
        "segments": len(payload["segments"]),
        "attributions": len(payload["attributions"]),
    }


def assessment(conn, ticker, accession, cutoff):
    from engine.settings import Settings

    empty: dict = {"segments": [], "attributions": []}
    if not Settings.from_env().dev_informational_feed:
        return empty
    row = (
        conn.execute(
            select(snapshots)
            .where(
                snapshots.c.ticker == ticker,
                snapshots.c.accession == accession,
                snapshots.c.available_at <= cutoff,
            )
            .order_by(snapshots.c.version.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    claim = known_filings(conn, ticker, cutoff).get(accession)
    if (
        not row
        or not claim
        or claim.get("source_status", "active") != "active"
        or source_identity(claim) != row["payload"]["source_identity"]
    ):
        return empty
    provenance = {
        "source_url": row["source_url"],
        "source_sha256": row["capture_sha256"],
        "snapshot_id": row["id"],
        "snapshot_version": row["version"],
        "captured_at": utc(row["captured_at"]).isoformat(),
        "available_at": utc(row["available_at"]).isoformat(),
    }
    return {kind: [{**item, **provenance} for item in row["payload"][kind]] for kind in empty}


def main():
    import argparse
    import json
    from pathlib import Path

    from engine.adapters.http_sources import AcquiredDocument
    from engine.db import database

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.collection.read_text(encoding="utf-8"))
    engine = database()
    report: dict = {"filings": {}, "errors": {}, "delivery": "disabled"}
    try:
        for row in receipt["filings"]:
            if row["form"] not in {"10-Q", "10-K", "10-Q/A", "10-K/A"}:
                continue
            key = row["ticker"] + ":" + row["accession"]
            try:
                path = (args.collection.parent / row["file"]).resolve()
                if not path.is_relative_to(args.collection.parent.resolve()):
                    raise ValueError("Cache path escapes collection")
                capture = AcquiredDocument(
                    row["url"],
                    path.read_text(encoding="utf-8"),
                    datetime.fromisoformat(row["retrieved_at"]),
                    row["content_sha256"],
                    hashlib.sha256(row["url"].encode()).hexdigest(),
                )
                with engine.connect() as conn:
                    claim = known_filings(conn, row["ticker"], datetime.now(UTC))[row["accession"]]
                report["filings"][key] = ingest(engine, claim, capture)
            except (ValueError, KeyError, ET.ParseError) as exc:
                report["errors"][key] = str(exc)
        print(json.dumps(report, indent=2))
    finally:
        engine.dispose()
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
