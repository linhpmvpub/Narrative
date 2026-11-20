"""Stage real SEC filing candidates for review; never backdate or approve evidence."""

import argparse
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

from engine.adapters.http_sources import SECSourceAdapter, SourceClient, SourceUnavailable
from engine.settings import Settings

TICKERS = ("MU", "NVDA", "AMD", "DELL", "SNDK")


def identities(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected SEC ticker object")
    result = {}
    for row in payload.values():
        if row.get("ticker") in TICKERS:
            ticker = row["ticker"]
            cik = str(row["cik_str"])
            if ticker in result or not re.fullmatch(r"[0-9]{1,10}", cik):
                raise ValueError("Ambiguous or invalid SEC identity")
            result[ticker] = {"cik": cik.zfill(10), "name": row["title"]}
    if set(result) != set(TICKERS) or len({v["cik"] for v in result.values()}) != 5:
        raise ValueError("Expected five distinct SEC issuer identities")
    return result


def candidates(ticker, cik, payload, start, end, per_company):
    if str(payload.get("cik", "")).zfill(10) != cik or ticker not in payload.get("tickers", []):
        raise ValueError("Submission CIK/ticker disagrees with SEC ticker index")
    recent = payload["filings"]["recent"]
    columns = [recent[key] for key in ("accessionNumber", "filingDate", "form", "primaryDocument")]
    if len({len(c) for c in columns}) != 1:
        raise ValueError("SEC recent-filing columns have different lengths")
    selected = []
    for accession, filed, form, document in zip(*columns, strict=True):
        filed_date = date.fromisoformat(filed)
        if not start <= filed_date <= end or form not in (
            "10-K",
            "10-Q",
            "8-K",
            "10-K/A",
            "10-Q/A",
            "8-K/A",
        ):
            continue
        if ticker == "SNDK" and filed_date < date(2025, 2, 21):
            continue
        if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
            raise ValueError("Invalid accession")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.html?", document):
            continue
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"
        selected.append(
            {
                "ticker": ticker,
                "cik": cik,
                "accession": accession,
                "filing_date": filed,
                "form": form,
                "url": url,
                "is_synthetic": False,
                "rights_status": "pending_review",
                "canonical_event_key": None,
                "label_status": "unlabeled",
                "historical_as_of_eligible": False,
            }
        )
    return sorted(selected, key=lambda r: (r["filing_date"], r["accession"]), reverse=True)[
        :per_company
    ]


def collect(client, output, start, end, per_company=10):
    if not 1 <= per_company <= 20 or start > end or end > datetime.now(UTC).date():
        raise ValueError("Invalid collection scope")
    output.mkdir(parents=True, exist_ok=False)
    report: dict = {
        "is_synthetic": False,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "status": "review_required",
        "delivery": "disabled",
        "identities": {},
        "filings": [],
        "errors": [],
    }

    def save():
        (output / "collection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    save()
    try:
        index = client.fetch("https://www.sec.gov/files/company_tickers.json")
        issuer_map = identities(json.loads(index.text))
        report["index_sha256"] = index.content_sha256
        report["index_retrieved_at"] = index.retrieved_at.isoformat()
        (output / "company_tickers.json").write_text(index.text, encoding="utf-8")
        for ticker, identity in issuer_map.items():
            document = SECSourceAdapter(client).submissions(identity["cik"])
            payload = json.loads(document.text)
            rows = candidates(ticker, identity["cik"], payload, start, end, per_company)
            report["identities"][ticker] = {
                **identity,
                "index_and_submissions_agree": True,
                "submission_sha256": document.content_sha256,
                "retrieved_at": document.retrieved_at.isoformat(),
                "production_identity_approval": "pending_review",
            }
            (output / f"{ticker}-submissions.json").write_text(document.text, encoding="utf-8")
            for row in rows:
                try:
                    filing = client.fetch(row["url"])
                    local = f"{ticker}-{row['accession']}.html"
                    (output / local).write_text(filing.text, encoding="utf-8")
                    report["filings"].append(
                        {
                            **row,
                            "file": local,
                            "content_sha256": filing.content_sha256,
                            "retrieved_at": filing.retrieved_at.isoformat(),
                            "first_available_to_engine_at": filing.retrieved_at.isoformat(),
                        }
                    )
                except SourceUnavailable:
                    report["errors"].append(
                        {"ticker": ticker, "url": row["url"], "reason": "source_unavailable"}
                    )
                save()
    finally:
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-agent", required=True, help="Real project name and contact email")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-company", type=int, default=10)
    args = parser.parse_args()
    Settings.from_env()
    client = SourceClient(user_agent=args.user_agent)
    try:
        result = collect(client, args.output, args.start, args.end, args.per_company)
        print(
            json.dumps(
                {
                    "downloaded_filings": len(result["filings"]),
                    "errors": len(result["errors"]),
                    "status": "review_required",
                    "historical_events_evaluated": 0,
                }
            )
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
