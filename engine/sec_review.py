"""Import already downloaded SEC filings into a separate, non-synthetic review DB.

No network, event publication, graph approval or notification side effect.
"""

import argparse
import hashlib
import json
import re
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import select

from engine.db import database
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode
from engine.models.schema_v5 import filings


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PlainText(HTMLParser):
    """Version-1 citation text; never return source HTML to the browser."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "ix:header", "ix:hidden"}:
            self.blocked.append(tag)
        if not self.blocked:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if self.blocked and tag == self.blocked[-1]:
            self.blocked.pop()
        if not self.blocked:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)


def plain_text(html):
    parser = PlainText()
    parser.feed(html)
    return " ".join("".join(parser.parts).split())


def require_real(conn):
    mode = conn.scalar(select(database_mode.c.mode))
    if mode != "production":
        raise ValueError("SEC review requires an explicitly separate production-mode database")


def initialize_review_store(engine):
    """Explicit opt-in only for an empty source store; never convert a demo database."""
    from sqlalchemy import func

    from engine.models.schema_v5 import metadata

    with engine.begin() as conn:
        mode = conn.scalar(select(database_mode.c.mode))
        if mode == "production":
            return
        if mode is not None:
            raise ValueError("Cannot use a synthetic database for real-source review")
        for name in ("rie_documents", "rie_sources", "rie_events", "rie_sec_filings"):
            if conn.scalar(select(func.count()).select_from(metadata.tables[name])):
                raise ValueError("Review initialization requires an empty source store")
        conn.execute(database_mode.insert().values(id=1, mode="production"))


def import_collection(engine, folder: Path):
    folder = folder.resolve()
    manifest = json.loads((folder / "collection.json").read_text(encoding="utf-8"))
    if manifest.get("is_synthetic") is not False or not 1 <= len(manifest["filings"]) <= 100:
        raise ValueError("Expected bounded real SEC collection")
    now = datetime.now(UTC)
    prepared = []
    for row in manifest["filings"]:
        ticker, accession = row["ticker"], row["accession"]
        if ticker not in {"MU", "NVDA", "AMD", "DELL", "SNDK"}:
            raise ValueError("Unknown pilot company")
        if row.get("is_synthetic") is not False or not re.fullmatch(
            r"\d{10}-\d{2}-\d{6}", accession
        ):
            raise ValueError("Invalid filing identity")
        identity = manifest["identities"][ticker]
        if str(row["cik"]) != str(identity["cik"]) or not identity["index_and_submissions_agree"]:
            raise ValueError("Unmatched acquisition identity")
        prefix = f"https://www.sec.gov/Archives/edgar/data/{int(row['cik'])}/{accession.replace('-', '')}/"
        if not row["url"].startswith(prefix) or not re.fullmatch(
            r"[A-Za-z0-9_.-]+", row["url"][len(prefix) :]
        ):
            raise ValueError("Unexpected SEC source URL")
        path = (folder / row["file"]).resolve()
        if (
            path.parent != folder
            or path.suffix.lower() != ".html"
            or path.stat().st_size > 6_000_000
        ):
            raise ValueError("Unsafe or oversized filing path")
        # Collector writes UTF-8 text using platform newline translation.
        html = path.read_text(encoding="utf-8")
        if sha(html) != row["content_sha256"]:
            raise ValueError("Filing content hash mismatch")
        retrieved = datetime.fromisoformat(row["retrieved_at"])
        if retrieved.tzinfo is None or retrieved > now:
            raise ValueError("Invalid capture time")
        if datetime.fromisoformat(row["first_available_to_engine_at"]) != retrieved:
            raise ValueError("Acquisition time mismatch")
        filed = date.fromisoformat(row["filing_date"])
        if filed > retrieved.date() or (ticker == "SNDK" and filed < date(2025, 2, 21)):
            raise ValueError("Invalid filing date or Sandisk separation")
        text = plain_text(html)
        if not text:
            raise ValueError("Empty source text")
        prepared.append(
            dict(
                id=sha(accession),
                ticker=ticker,
                accession=accession,
                source_url=row["url"],
                content_sha256=row["content_sha256"],
                text_sha256=sha(text),
                source_text=text,
                retrieved_at=retrieved,
                imported_at=now,
                manifest={
                    **row,
                    "text_transform": "html-to-text-v1",
                    "rights_status": "pending_review",
                },
                revision=0,
            )
        )
    inserted = 0
    with engine.begin() as conn:
        require_real(conn)
        for row in prepared:
            old = conn.execute(select(filings).where(filings.c.id == row["id"])).mappings().first()
            if old:
                if (
                    any(
                        old[k] != row[k]
                        for k in ("ticker", "source_url", "content_sha256", "text_sha256")
                    )
                    or utc(old["retrieved_at"]) != row["retrieved_at"]
                ):
                    raise ValueError("Existing capture cannot be overwritten")
                continue
            conn.execute(filings.insert().values(**row))
            inserted += 1
    return {
        "inserted": inserted,
        "unchanged": len(prepared) - inserted,
        "reviewed_events": 0,
        "feed_publications": 0,
        "delivery": "disabled",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--initialize-review-store", action="store_true")
    args = parser.parse_args()
    engine = database()
    try:
        if args.initialize_review_store:
            initialize_review_store(engine)
        print(json.dumps(import_collection(engine, args.folder)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
