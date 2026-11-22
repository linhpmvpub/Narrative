"""RSS/Atom and official X read adapters. External text is never an instruction."""

import hashlib
import ipaddress
import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


def public_url(value):
    p = urlsplit(value)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("Invalid public URL")
    if p.port not in (None, 80, 443) or "." not in p.hostname or p.hostname.endswith(".local"):
        raise ValueError("Invalid public host")
    try:
        address = ipaddress.ip_address(p.hostname)
    except ValueError:
        address = None
    if address is not None:
        raise ValueError("IP literal not allowed")
    return value


def canonical_url(value):
    p = urlsplit(public_url(value))
    query = [
        (k, v)
        for k, v in parse_qsl(p.query)
        if not k.lower().startswith("utm_")
        and k.lower() not in {"guccounter", "guce_referrer", "fbclid", "gclid"}
    ]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, urlencode(sorted(query)), ""))


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value, limit=600):
    parser = Text()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())[:limit]


def published(value, now):
    if not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            return None
    if when.tzinfo is None:
        return None
    when = when.astimezone(UTC)
    if when > now + timedelta(minutes=5):
        raise ValueError("Publication timestamp in future")
    return when.isoformat()


def parse_feed(body, now):
    decoded = body.decode("utf-8-sig")
    if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ValueError("DTD/entities forbidden")
    try:
        root = ET.fromstring(decoded)
    except ET.ParseError:
        raise ValueError("Malformed XML") from None
    if root.tag.rsplit("}", 1)[-1] not in {"rss", "feed", "RDF"}:
        raise ValueError("Not RSS or Atom")
    rows, rejected = [], 0
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
            continue
        fields = {c.tag.rsplit("}", 1)[-1]: "".join(c.itertext()) for c in node}
        links = [c for c in node if c.tag.rsplit("}", 1)[-1] == "link"]
        link = next(
            (
                c.get("href")
                for c in links
                if c.get("rel", "alternate") == "alternate" and c.get("href")
            ),
            fields.get("link", ""),
        )
        try:
            url = canonical_url(link)
            title = plain(fields.get("title"), 400)
            if not title:
                raise ValueError("Missing title")
            rows.append(
                {
                    "external_id": (fields.get("guid") or fields.get("id") or url)[:1000],
                    "url": url,
                    "title": title,
                    "summary": plain(fields.get("description") or fields.get("summary")),
                    "published_at": published(
                        fields.get("pubDate")
                        or fields.get("published")
                        or fields.get("updated")
                        or fields.get("date"),
                        now,
                    ),
                }
            )
        except ValueError:
            rejected += 1
        if len(rows) + rejected >= 500:
            raise ValueError("Feed exceeds bounded item count")
    if rejected and not rows:
        raise ValueError("No valid entries")
    return rows, rejected


class FetchError(Exception):
    def __init__(self, status, retry=300):
        self.status, self.retry = status, retry


class NewsClient:
    def __init__(self, *, token=None, transport=None):
        self.token = token
        self.client = httpx.Client(
            timeout=20,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": "NarrativeNewsReader/0.1"},
        )

    def close(self):
        self.client.close()

    def get(self, url, *, headers=None, params=None, authenticated=False):
        public_url(url)
        headers = dict(headers or {})
        if authenticated:
            if urlsplit(url).hostname != "api.x.com" or not self.token:
                raise FetchError("X_NOT_CONFIGURED", 3600)
            headers["Authorization"] = "Bearer " + self.token
        try:
            with self.client.stream("GET", url, headers=headers, params=params) as response:
                if response.status_code == 304:
                    return b"", response.headers, 304
                if response.status_code != 200:
                    delay = response.headers.get("retry-after", "300")
                    delay = int(delay) if delay.isdigit() else 300
                    raise FetchError(
                        "HTTP_" + str(response.status_code), min(86400, max(60, delay))
                    )
                parts, length = [], 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > 3_000_000:
                        raise FetchError("RESPONSE_TOO_LARGE")
                    parts.append(chunk)
                return b"".join(parts), response.headers, 200
        except httpx.HTTPError:
            raise FetchError("NETWORK_UNAVAILABLE") from None

    def fetch(self, config, state, now):
        if config["kind"] == "rss":
            headers = {}
            for key, header in (("etag", "If-None-Match"), ("modified", "If-Modified-Since")):
                if state.get(key):
                    headers[header] = state[key]
            body, response_headers, status = self.get(config["url"], headers=headers)
            if status == 304:
                return [], state, None, "NOT_MODIFIED", 0
            rows, rejected = parse_feed(body, now)
            return (
                rows,
                {
                    "etag": response_headers.get("etag"),
                    "modified": response_headers.get("last-modified"),
                },
                hashlib.sha256(body).hexdigest(),
                "OK",
                rejected,
            )
        # Explicitly disabled unless the worker was configured to allow X.
        if not self.token:
            raise FetchError("X_NOT_CONFIGURED", 3600)
        handle = config["handle"]
        if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
            raise ValueError("Invalid X handle")
        user_id = state.get("user_id")
        if not user_id:
            body, _, _ = self.get(
                "https://api.x.com/2/users/by/username/" + handle, authenticated=True
            )
            data = json.loads(body)["data"]
            if data["username"].casefold() != handle.casefold() or not str(data["id"]).isdigit():
                raise ValueError("X identity mismatch")
            user_id = data["id"]
        rows, hashes, cursor = [], [], None
        for _ in range(5):
            params = {
                "max_results": 100,
                "tweet.fields": "created_at,author_id,edit_history_tweet_ids",
                "exclude": "retweets,replies",
            }
            if state.get("since_id"):
                params["since_id"] = state["since_id"]
            if cursor:
                params["pagination_token"] = cursor
            body, _, _ = self.get(
                f"https://api.x.com/2/users/{user_id}/tweets", params=params, authenticated=True
            )
            payload = json.loads(body)
            if payload.get("errors"):
                raise FetchError("X_PARTIAL_RESPONSE")
            hashes.append(hashlib.sha256(body).hexdigest())
            for post in payload.get("data", []):
                if post["author_id"] != user_id or not post["id"].isdigit():
                    raise ValueError("X post identity mismatch")
                rows.append(
                    {
                        "external_id": post["id"],
                        "url": f"https://x.com/{handle}/status/{post['id']}",
                        "title": plain(post["text"], 400),
                        "summary": "",
                        "published_at": published(post.get("created_at"), now),
                    }
                )
            cursor = payload.get("meta", {}).get("next_token")
            if not cursor:
                break
        if cursor:
            raise FetchError("X_BACKLOG_EXCEEDS_PAGE_CAP", 3600)
        since = max([int(r["external_id"]) for r in rows] + [int(state.get("since_id", 0))])
        return (
            rows,
            {"user_id": user_id, "since_id": str(since)},
            hashlib.sha256("".join(hashes).encode()).hexdigest(),
            "OK",
            0,
        )
