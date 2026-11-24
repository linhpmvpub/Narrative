"""Official SEC metadata discovery alongside existing RSS; never canonical ingestion."""

import hashlib
import json
import re
from datetime import timedelta

from engine.adapters.news import FetchError, NewsClient, published
from engine.collect_sec import TICKERS, candidates
from engine.news_capture import archive_capture


def validate_sec_source(config):
    cik = str(config.get("cik", ""))
    if (
        not re.fullmatch(r"[0-9]{10}", cik)
        or int(cik) == 0
        or config.get("ticker") not in TICKERS
        or config.get("url") != f"https://data.sec.gov/submissions/CIK{cik}.json"
        or not 1 <= config.get("lookback_days", 30) <= 90
    ):
        raise ValueError("Explicit SEC issuer and bounded source URL required")


class MarketClient(NewsClient):
    def __init__(self, *, user_agent, **kwargs):
        if not re.fullmatch(r"[^\r\n]+\s+[^\s@]+@[^\s@]+\.[^\s@]+", user_agent):
            raise ValueError("Contact User-Agent required")
        super().__init__(**kwargs)
        self.client.headers["User-Agent"] = user_agent

    def fetch(self, config, state, now):
        if config["kind"] != "sec_submissions":
            return super().fetch(config, state, now)
        validate_sec_source(config)
        headers = {
            h: state[k]
            for k, h in [("etag", "If-None-Match"), ("modified", "If-Modified-Since")]
            if state.get(k)
        }
        body, response, code = self.get(config["url"], headers=headers)
        if code == 304:
            return [], state, None, "NOT_MODIFIED", 0
        if self.capture_dir is not None:
            try:
                archive_capture(self.capture_dir, body, ".json")
            except (OSError, ValueError):
                raise FetchError("CAPTURE_ARCHIVE_FAILED") from None
        payload = json.loads(body)
        filings = candidates(
            config["ticker"],
            config["cik"],
            payload,
            now.date() - timedelta(days=config.get("lookback_days", 30)),
            now.date(),
            201,
        )
        if len(filings) > 200:
            raise FetchError("SEC_WINDOW_TRUNCATED")
        recent = payload["filings"]["recent"]
        accession_index = {a: i for i, a in enumerate(recent["accessionNumber"])}
        rows = []
        for filing in filings:
            i = accession_index[filing["accession"]]
            dates = recent.get("acceptanceDateTime", [])
            period = recent.get("reportDate", [])
            rows.append(
                {
                    "external_id": filing["accession"],
                    "url": filing["url"],
                    "title": f"{config['ticker']} filed {filing['form']}",
                    "summary": f"SEC filing metadata only. Filed {filing['filing_date']}; content awaits extraction and review.",
                    "published_at": published(dates[i], now) if i < len(dates) else None,
                    "filing_date": filing["filing_date"],
                    "report_period": period[i] if i < len(period) else None,
                    "cik": config["cik"],
                    "ticker": config["ticker"],
                    "form": filing["form"],
                    "is_amendment": filing["form"].endswith("/A"),
                    "filing_metadata_only": True,
                }
            )
        return (
            rows,
            {"etag": response.get("etag"), "modified": response.get("last-modified")},
            hashlib.sha256(body).hexdigest(),
            "OK",
            0,
        )
