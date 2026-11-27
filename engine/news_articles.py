"""Private article packets: explicit local capture, no automatic claim promotion."""

import argparse
import json
import os
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

from engine.adapters.news import NewsClient, public_url
from engine.db import database
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v13 import news_revisions
from engine.news_capture import archive_capture, read_capture

HOSTS = {
    "blogs.nvidia.com",
    "www.dell.com",
    "www.sec.gov",
    "news.skhynix.com",
    "www.eia.gov",
    "www.datacenterdynamics.com",
    "www.datacenterknowledge.com",
    "www.cnbc.com",
    "www.marketwatch.com",
    "www.federalreserve.gov",
    "www.ecb.europa.eu",
    "nvidianews.nvidia.com",
    "investors.micron.com",
    "micron.gcs-web.com",
    "www.sandisk.com",
    "ir.amd.com",
    "investors.delltechnologies.com",
    "investor.sandisk.com",
}


def root_dir():
    return Path(os.getenv("NEWS_ARTICLE_DIR", "source-cache/news-articles"))


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "template"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(" ".join(data.split()))


def normalized_text(body):
    parser = VisibleText()
    parser.feed(body.decode("utf-8-sig"))
    return "\n".join(parser.parts)


def capture(revision, client, *, url=None, relation="same_article", root=None):
    url = url or revision["payload"]["url"]
    public_url(url)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise ValueError("Article host not allowlisted")
    if relation not in {"same_article", "issuer_context"}:
        raise ValueError("Unknown evidence relation")
    if relation == "same_article" and url != revision["payload"]["url"]:
        raise ValueError("Article URL must exactly match pinned revision")
    body, headers, status = client.get(url)
    if status != 200 or "html" not in headers.get("content-type", "").lower():
        raise ValueError("Expected HTTP200 HTML")
    now = datetime.now(UTC)
    if utc(revision["received_at"]) > now:
        raise ValueError("Revision unavailable")
    text = normalized_text(body)
    if not text.strip():
        raise ValueError("Empty article text")
    root = Path(root) if root is not None else root_dir()
    packet = {
        "schema": "ARTICLE_PACKET_V1",
        "revision_id": revision["id"],
        "payload_sha256": digest(revision["payload"]),
        "url": url,
        "relation": relation,
        "retrieved_at": now.isoformat(),
        "body_sha256": archive_capture(root / "bodies", body, ".html"),
        "text_sha256": archive_capture(root / "texts", text.encode(), ".txt"),
        "text_basis": "VISIBLE_HTML_TEXT_V1_NOT_ARTICLE_ONLY",
        "http_status": status,
        "independent_corroboration": False,
        "review_status": "UNREVIEWED",
        "impact_eligible": False,
    }
    sha = archive_capture(
        root / digest(revision["id"]), json.dumps(packet, sort_keys=True).encode(), ".json"
    )
    return {**packet, "packet_sha256": sha}


def read_packet(revision, sha, *, root=None):
    root = Path(root) if root is not None else root_dir()
    try:
        packet = json.loads(read_capture(root / digest(revision["id"]), sha, ".json"))
    except OSError:
        raise ValueError("Article packet unavailable") from None
    public_url(packet["url"])
    parsed = urlsplit(packet["url"])
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or packet["relation"] not in {"same_article", "issuer_context"}
        or packet["http_status"] != 200
    ):
        raise ValueError("Invalid article provenance")
    if (
        packet["schema"] != "ARTICLE_PACKET_V1"
        or packet["revision_id"] != revision["id"]
        or packet["payload_sha256"] != digest(revision["payload"])
    ):
        raise ValueError("Article revision mismatch")
    at = datetime.fromisoformat(packet["retrieved_at"])
    if at.tzinfo is None or not utc(revision["received_at"]) <= at <= datetime.now(UTC):
        raise ValueError("Article chronology invalid")
    if packet["relation"] == "same_article" and packet["url"] != revision["payload"]["url"]:
        raise ValueError("Article URL mismatch")
    try:
        body = read_capture(root / "bodies", packet["body_sha256"], ".html")
        text = read_capture(root / "texts", packet["text_sha256"], ".txt").decode()
    except OSError:
        raise ValueError("Article bytes unavailable") from None
    if normalized_text(body) != text:
        raise ValueError("Article text mismatch")
    return packet, text


def evidence(revision):
    directory = root_dir() / digest(revision["id"])
    files = sorted(directory.glob("*.json")) if directory.exists() else []
    rows = []
    for path in files[:20]:
        try:
            packet, _ = read_packet(revision, path.stem)
            rows.append(
                {
                    k: packet[k]
                    for k in (
                        "url",
                        "relation",
                        "retrieved_at",
                        "body_sha256",
                        "text_sha256",
                        "text_basis",
                    )
                }
                | {"packet_sha256": path.stem, "status": "INTEGRITY_CHECKED_UNREVIEWED"}
            )
        except (OSError, ValueError, KeyError, TypeError):
            rows.append({"packet_sha256": path.stem, "status": "INVALID_OR_UNAVAILABLE"})
    return {
        "items": rows,
        "truncated": len(files) > 20,
        "independent_corroboration": False,
        "availability_basis": "RETRIEVED_AT_NOT_RSS_PUBLICATION",
        "impact_eligible": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision_id")
    parser.add_argument("--url")
    parser.add_argument(
        "--relation", choices=["same_article", "issuer_context"], default="same_article"
    )
    args = parser.parse_args()
    engine = database()
    with engine.connect() as conn:
        revision = (
            conn.execute(select(news_revisions).where(news_revisions.c.id == args.revision_id))
            .mappings()
            .one()
        )
    client = NewsClient()
    try:
        result = capture(revision, client, url=args.url, relation=args.relation)
        print(json.dumps(result))
    finally:
        client.close()
        engine.dispose()


if __name__ == "__main__":
    main()
