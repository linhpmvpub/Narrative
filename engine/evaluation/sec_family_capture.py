"""Capture same-accession SEC attachments for review, never automatic promotion."""

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from engine.adapters.http_sources import SourceClient, SourceUnavailable
from engine.evaluation.held_role_corpus import checked, read
from engine.ingestion.contracts import digest


def exact_capture(root, name, expected):
    checked(root, name, expected)  # containment and UTF-8 validation
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
        raise ValueError("Stored capture bytes changed")


def family_url(source, url):
    """No userinfo, encoded paths, redirects, traversal or cross-accession links."""
    prefix = (f"/Archives/edgar/data/{int(source['cik'])}/"
              f"{source['accession'].replace('-', '')}/")
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.netloc == "www.sec.gov"
            and not parsed.query and not parsed.fragment
            and parsed.path.startswith(prefix)
            and re.fullmatch(r"[A-Za-z0-9_.-]+\.html?", parsed.path[len(prefix):]) is not None)


def plan(directory, root):
    receipt = read(directory / "freeze.json")
    rows = read(directory / "source-audit.json")
    if digest(rows) != receipt.get("source_audit_sha256"):
        raise ValueError("Source audit changed")
    families = []
    for row in rows:
        if row["status"] not in {"EVENT_AND_EXHIBIT_REVIEW_REQUIRED",
                                 "AMENDMENT_FAMILY_REVIEW_REQUIRED"}:
            continue
        source = row["source"]
        directory_path = (root / source["collection_directory"]).resolve()
        if not directory_path.is_relative_to(root.resolve()):
            raise ValueError("Source directory escapes root")
        exact_capture(directory_path, source["file"], source["stored_bytes_sha256"])
        if not family_url(source, source["url"]):
            raise ValueError("Invalid primary SEC URL")
        links = sorted(set(row["linked_documents"]))
        if len(links) > 100 or any(not family_url(source, link) for link in links):
            raise ValueError("Invalid or excessive attachment links")
        # Amendment scope is reviewed from primary documents, not all annual-report exhibits.
        if row["status"] == "AMENDMENT_FAMILY_REVIEW_REQUIRED":
            links = []
        families.append({"source": source, "required_review": row["status"],
                         "attachment_urls": links})
    if sum(len(r["attachment_urls"]) for r in families) > 200:
        raise ValueError("Attachment request budget exceeded")
    return {"source_audit_sha256": digest(rows), "families": families,
            "delivery": "disabled", "ingested": False}


def capture(directory, root, output, client):
    scope = plan(directory, root)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "collection.json"
    manifest = read(path) if path.exists() else {
        "plan_sha256": digest(scope), "source_audit_sha256": scope["source_audit_sha256"],
        "captures": {}, "errors": {}, "delivery": "disabled", "ingested": False}
    if manifest["plan_sha256"] != digest(scope):
        raise ValueError("Capture plan changed; use a new directory")
    urls = {url for row in scope["families"] for url in row["attachment_urls"]}
    if not set(manifest["captures"]) <= urls:
        raise ValueError("Unplanned capture")
    for url, item in manifest["captures"].items():
        exact_capture(output, item["file"], item["content_sha256"])
        at = datetime.fromisoformat(item["retrieved_at"])
        if item["url"] != url or at.tzinfo is None or at > datetime.now(UTC):
            raise ValueError("Invalid capture provenance")

    def save():
        temp = output / "collection.tmp"
        temp.write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
        temp.replace(path)

    save()
    for url in sorted(urls):
        if url in manifest["captures"]:
            continue
        try:
            doc = client.fetch(url)
            if (doc.url != url or hashlib.sha256(doc.text.encode()).hexdigest() != doc.content_sha256
                    or doc.retrieved_at.tzinfo is None or doc.retrieved_at > datetime.now(UTC)):
                raise ValueError("Invalid fetched source provenance")
            name = hashlib.sha256(url.encode()).hexdigest() + ".html"
            with (output / name).open("xb") as stream:
                stream.write(doc.text.encode())
            manifest["captures"][url] = {"url": url, "file": name,
                "content_sha256": doc.content_sha256, "retrieved_at": doc.retrieved_at.isoformat(),
                "rights_status": "pending_review", "is_synthetic": False}
            manifest["errors"].pop(url, None)
        except SourceUnavailable:
            manifest["errors"][url] = "SOURCE_UNAVAILABLE"
        save()
    manifest["families"] = []
    for row in scope["families"]:
        missing = [u for u in row["attachment_urls"] if u not in manifest["captures"]]
        status = ("AMENDMENT_SCOPE_REVIEW_REQUIRED" if row["required_review"]
                  == "AMENDMENT_FAMILY_REVIEW_REQUIRED" else "ATTACHMENT_REVIEW_REQUIRED")
        manifest["families"].append({**row, "missing_urls": missing,
            "status": "INCOMPLETE_CAPTURE" if missing else status,
            "complete_exhibit_inventory_verified": False,
            "available_at": max(datetime.fromisoformat(t) for t in
                [row["source"]["first_available_to_engine_at"]] + [
                manifest["captures"][u]["retrieved_at"] for u in row["attachment_urls"]
                if u in manifest["captures"]]).isoformat()})
    save()
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--user-agent", required=True)
    args = parser.parse_args()
    client = SourceClient(user_agent=args.user_agent)
    try:
        result = capture(args.audit, args.root, args.output, client)
        print(json.dumps({"families": len(result["families"]),
                          "captured": len(result["captures"]), "errors": len(result["errors"]),
                          "delivery": "disabled", "ingested": False}))
    finally:
        client.close()
