import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from engine.adapters.http_sources import SourceUnavailable
from engine.evaluation.sec_family_capture import capture, family_url, plan
from engine.ingestion.contracts import digest


@pytest.fixture
def family(tmp_path):
    source = {"cik": "0000000001", "accession": "0000000001-26-000001",
              "url": "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/main.htm",
              "collection_directory": "source", "file": "main.htm",
              "first_available_to_engine_at": "2026-01-01T00:00:00+00:00"}
    raw = b'<a href="ex99.htm">Exhibit</a>'
    (tmp_path / "source").mkdir()
    (tmp_path / "source/main.htm").write_bytes(raw)
    source["stored_bytes_sha256"] = hashlib.sha256(raw).hexdigest()
    url = source["url"].replace("main.htm", "ex99.htm")
    rows = [{"status": "EVENT_AND_EXHIBIT_REVIEW_REQUIRED", "source": source,
             "linked_documents": [url]}]
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "source-audit.json").write_text(json.dumps(rows))
    (audit / "freeze.json").write_text(json.dumps({"source_audit_sha256": digest(rows)}))
    return tmp_path, audit, source, url


class Client:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def fetch(self, url):
        self.calls += 1
        if self.fail:
            raise SourceUnavailable("Synthetic unavailable")
        text = "<p>Synthetic exhibit.</p>\n"
        return SimpleNamespace(url=url, text=text, content_sha256=hashlib.sha256(text.encode()).hexdigest(),
                               retrieved_at=datetime.now(UTC))


@pytest.mark.parametrize("suffix", ["../other.htm", "a/b.htm", "%2e%2e/evil.htm", "x.htm?q=1",
                                    "x.htm#part", "x.pdf"])
def test_reject_unsafe_or_unsupported_links(family, suffix):
    _, _, source, _ = family
    assert not family_url(source, source["url"].replace("main.htm", suffix))
    assert not family_url(source, source["url"].replace("www.sec.gov", "evil.test"))


def test_capture_resume_no_refetch_no_approval(family):
    root, audit, _, url = family
    client = Client()
    out = root / "out"
    first = capture(audit, root, out, client)
    second = capture(audit, root, out, client)
    assert client.calls == 1 and first == second
    assert second["captures"][url]["rights_status"] == "pending_review"
    row = second["families"][0]
    assert row["status"] == "ATTACHMENT_REVIEW_REQUIRED"
    assert not row["complete_exhibit_inventory_verified"]
    assert datetime.fromisoformat(row["available_at"]) >= datetime.fromisoformat(
        second["captures"][url]["retrieved_at"])
    assert not second["ingested"] and second["delivery"] == "disabled"


def test_missing_attachment_not_ready_and_retry_recovers(family):
    root, audit, _, url = family
    out = root / "out"
    bad = capture(audit, root, out, Client(fail=True))
    assert bad["families"][0]["status"] == "INCOMPLETE_CAPTURE"
    assert bad["families"][0]["missing_urls"] == [url]
    good = capture(audit, root, out, Client())
    assert good["errors"] == {} and not good["families"][0]["missing_urls"]


def test_changed_audit_or_capture_rejected(family):
    root, audit, _, url = family
    out = root / "out"
    result = capture(audit, root, out, Client())
    (out / result["captures"][url]["file"]).write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        capture(audit, root, out, Client())
    (audit / "source-audit.json").write_text("[]")
    with pytest.raises(ValueError, match="audit"):
        plan(audit, root)


def test_amendment_primary_only_and_no_automatic_release(family):
    root, audit, _, _ = family
    rows = json.loads((audit / "source-audit.json").read_text())
    rows[0]["status"] = "AMENDMENT_FAMILY_REVIEW_REQUIRED"
    (audit / "source-audit.json").write_text(json.dumps(rows))
    (audit / "freeze.json").write_text(json.dumps({"source_audit_sha256": digest(rows)}))
    client = Client()
    result = capture(audit, root, root / "out", client)
    assert client.calls == 0
    assert result["families"][0]["status"] == "AMENDMENT_SCOPE_REVIEW_REQUIRED"
