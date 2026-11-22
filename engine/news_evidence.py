"""Current local byte checks for review packets, never historical proof or approval."""

import os

from engine.adapters.news import parse_feed
from engine.models.contracts import utc
from engine.news_capture import read_capture


def capture_evidence(revision):
    sha = revision["capture_sha256"]
    result = {
        "capture_sha256": sha,
        "status": "UNAVAILABLE",
        "byte_integrity": False,
        "revision_content_match": False,
        "availability_basis": "LOCAL_CHECK_NOW_NOT_ORIGINAL_CAPTURE_TIME",
        "parser_basis": "CURRENT_RSS_PARSER",
        "article_evidence": "NOT_ATTACHED",
        "independent_corroboration": False,
    }
    if revision["payload"].get("kind") != "rss":
        return {**result, "status": "UNSUPPORTED_SOURCE_KIND"}
    try:
        body = read_capture(os.getenv("NEWS_CAPTURE_DIR", "source-cache/rss-captures"), sha)
    except FileNotFoundError:
        return result
    except ValueError:
        return {**result, "status": "INTEGRITY_FAILED"}
    except OSError:
        return {**result, "status": "UNREADABLE"}
    result.update(byte_integrity=True, byte_count=len(body))
    try:
        rows, _ = parse_feed(body, utc(revision["received_at"]))
    except (ValueError, TypeError):
        return {**result, "status": "PARSE_FAILED"}
    payload = revision["payload"]
    keys = ("external_id", "url", "title", "summary", "published_at")
    matches = [r for r in rows if r["external_id"] == payload.get("external_id")]
    # Multiple entries sharing a GUID are ambiguous even when one matches.
    matched = len(matches) == 1 and all(matches[0].get(k) == payload.get(k) for k in keys)
    return {
        **result,
        "status": "BYTES_AND_ENTRY_MATCH" if matched else "ENTRY_MISMATCH_OR_AMBIGUOUS",
        "revision_content_match": matched,
    }
