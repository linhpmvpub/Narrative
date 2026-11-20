"""Bounded, explicit source acquisition. No inferred facts or automatic live ingestion."""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Callable
from urllib.parse import urlparse

import httpx


class SourceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AcquiredDocument:
    url: str
    text: str
    retrieved_at: datetime
    content_sha256: str
    url_sha256: str
    rights_status: str = "approved"


class SourceClient:
    """Serial requests, <=2/sec, bounded retries and immutable disk snapshots.

    A historical request may ONLY use a snapshot retrieved before its cutoff.
    Fetching today's aggregate SEC response cannot reconstruct yesterday's view.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        cache_dir: Path | None = None,
        transport=None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        if not re.fullmatch(r"[^\r\n]+\s+[^\s@]+@[^\s@]+\.[^\s@]+", user_agent):
            raise ValueError("Descriptive User-Agent with contact email required")
        self.client = httpx.Client(
            transport=transport,
            timeout=15,
            follow_redirects=False,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )
        self.cache_dir = cache_dir
        self.monotonic, self.sleep, self.now = monotonic, sleep, now
        self.next_request = 0.0
        self.lock = Lock()
        self.snapshots: list[AcquiredDocument] = []
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
            for path in cache_dir.glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                item = AcquiredDocument(
                    **{**payload, "retrieved_at": datetime.fromisoformat(payload["retrieved_at"])}
                )
                if (
                    hashlib.sha256(item.text.encode()).hexdigest() != item.content_sha256
                    or hashlib.sha256(item.url.encode()).hexdigest() != item.url_sha256
                ):
                    raise ValueError("Corrupt source cache")
                self.snapshots.append(item)

    def close(self) -> None:
        self.client.close()

    def fetch(self, url: str, *, as_of: datetime | None = None) -> AcquiredDocument:
        if as_of is not None and as_of.tzinfo is None:
            raise ValueError("as_of must be timezone aware")
        with self.lock:
            cutoff = as_of or self.now()
            cached = [x for x in self.snapshots if x.url == url and x.retrieved_at <= cutoff]
            if cached:
                latest = max(cached, key=lambda x: x.retrieved_at)
                if as_of is not None or cutoff - latest.retrieved_at <= timedelta(minutes=5):
                    return latest
            if as_of is not None:
                raise SourceUnavailable(
                    "No source snapshot existed at as_of; network replay forbidden"
                )
            for attempt in range(4):
                self.sleep(max(0, self.next_request - self.monotonic()))
                self.next_request = self.monotonic() + 0.5
                try:
                    with self.client.stream("GET", url) as response:
                        if response.status_code == 429 or 500 <= response.status_code < 600:
                            delay = min(
                                30.0, float(response.headers.get("Retry-After", 2**attempt))
                            )
                            if delay < 0:
                                delay = 0
                            self.sleep(delay)
                            continue
                        response.raise_for_status()  # includes redirects; never follow off-allowlist
                        chunks, length = [], 0
                        for chunk in response.iter_bytes():
                            length += len(chunk)
                            if length > 5_000_000:
                                raise SourceUnavailable("Response exceeds 5MB decoded limit")
                            chunks.append(chunk)
                        text = b"".join(chunks).decode("utf-8")
                        item = AcquiredDocument(
                            url,
                            text,
                            self.now(),
                            hashlib.sha256(text.encode()).hexdigest(),
                            hashlib.sha256(url.encode()).hexdigest(),
                        )
                        if self.cache_dir:
                            path = self.cache_dir / (
                                item.url_sha256
                                + "-"
                                + item.retrieved_at.strftime("%Y%m%d%H%M%S%f")
                                + ".json"
                            )
                            payload = {
                                **item.__dict__,
                                "retrieved_at": item.retrieved_at.isoformat(),
                            }
                            temp = path.with_suffix(".tmp")
                            temp.write_text(json.dumps(payload), encoding="utf-8")
                            temp.replace(path)
                        self.snapshots.append(item)
                        return item
                except (httpx.TimeoutException, httpx.NetworkError):
                    self.sleep(2**attempt)
                except (httpx.HTTPStatusError, UnicodeError, ValueError) as exc:
                    raise SourceUnavailable("Source fetch failed; no event produced") from exc
            raise SourceUnavailable("Source retry budget exhausted; no event produced")


class SECSourceAdapter:
    def __init__(self, client: SourceClient):
        self.client = client

    def _get(self, cik: str, kind: str, as_of: datetime | None) -> AcquiredDocument:
        if not re.fullmatch(r"\d{1,10}", cik):
            raise ValueError("CIK must be 1–10 digits, verified separately")
        prefix = "submissions" if kind == "submissions" else "api/xbrl/companyfacts"
        result = self.client.fetch(
            f"https://data.sec.gov/{prefix}/CIK{int(cik):010d}.json", as_of=as_of
        )
        try:
            payload = json.loads(result.text)
            if not isinstance(payload, dict) or int(payload.get("cik", -1)) != int(cik):
                raise ValueError("SEC response issuer mismatch")
            if kind == "companyfacts" and not isinstance(payload.get("facts"), dict):
                raise ValueError("Missing CompanyFacts")
            if kind == "submissions" and not isinstance(payload.get("filings"), dict):
                raise ValueError("Missing submissions")
        except (ValueError, TypeError) as exc:
            raise SourceUnavailable("Invalid SEC JSON; no event produced") from exc
        return result

    def submissions(self, cik: str, *, as_of: datetime | None = None) -> AcquiredDocument:
        return self._get(cik, "submissions", as_of)

    def companyfacts(self, cik: str, *, as_of: datetime | None = None) -> AcquiredDocument:
        return self._get(cik, "companyfacts", as_of)


@dataclass(frozen=True)
class IRApproval:
    origin: str
    rights_status: str
    reviewer: str
    rights_note: str
    approved_at: datetime


class IRSourceAdapter:
    def __init__(self, client: SourceClient, approvals: list[IRApproval]):
        self.client, self.approvals = client, approvals

    def fetch(self, url: str, *, as_of: datetime | None = None) -> AcquiredDocument:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("IR requires HTTPS on the approved origin")
        origin = f"https://{parsed.hostname}"
        at = as_of or self.client.now()
        if not any(
            x.origin == origin
            and x.rights_status == "approved"
            and x.reviewer.strip()
            and x.rights_note.strip()
            and x.approved_at.tzinfo is not None
            and x.approved_at <= at
            for x in self.approvals
        ):
            raise ValueError("IR origin lacks source-backed rights approval at as_of")
        return self.client.fetch(url, as_of=as_of)
