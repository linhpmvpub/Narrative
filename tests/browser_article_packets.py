"""Read-only operator dossier check against the local private development API."""

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
token = (ROOT / "secrets/development-operator-access-token.txt").read_text().strip()


def get(path):
    req = urllib.request.Request(
        "http://127.0.0.1:8888" + path, headers={"Authorization": "Bearer " + token}
    )
    with urllib.request.urlopen(req) as response:
        return json.load(response)


items = get("/api/v0/news?limit=200")["items"]
selected = None
for item in items:
    if item.get("url") != "https://www.cnbc.com/2026/11/20/treasury-secretary-scott-bessent.html":
        continue
    src = get("/api/v0/news-claims/source/" + item["id"])
    dossier = get(
        "/api/v0/news-claims/source/"
        + item["id"]
        + "/dossier?"
        + urllib.parse.urlencode(
            {"ticker": "NVDA", "expected_payload_sha256": src["payload_sha256"]}
        )
    )
    if dossier["article_evidence"]["items"]:
        selected = item
        break
assert selected is not None
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8888/news-review")
    page.locator("#token").fill(token)
    page.locator("#login button").click()
    expect(page.locator("#workspace")).to_be_visible()
    page.locator("#item").select_option(selected["id"])
    page.locator("#load").click()
    expect(page.locator("#source")).not_to_have_value("")
    page.locator("#ticker").select_option("NVDA")
    page.locator("#load-dossier").click()
    expect(page.locator("#dossier-result")).to_contain_text("Bản RSS:")
    expect(page.locator("#dossier-result")).to_contain_text(
        dossier["raw_source_evidence"]["status"]
    )
    expect(page.locator("#dossier-result")).to_contain_text("issuer_context")
    article = page.locator("#dossier-result article").filter(has_text="issuer_context")
    article.get_by_role("button", name="Trích ứng viên số liệu").click()
    expect(article.locator("pre")).to_contain_text("UNREVIEWED_EXTRACTION_CANDIDATE")
    expect(article.locator("pre")).to_contain_text("UNRESOLVED")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#logout").click()
    expect(page.locator("#dossier-result")).to_be_empty()
    assert not errors
    browser.close()
checked = 0
for line in (ROOT / "MANIFEST_SHA256.txt").read_text().splitlines():
    if line.strip():
        sha, name = line.split(maxsplit=1)
        assert hashlib.sha256((ROOT / name.lstrip("*")).read_bytes()).hexdigest() == sha
        checked += 1
report = {
    "article_packets": len(dossier["article_evidence"]["items"]),
    "mobile_width": 390,
    "overflow": False,
    "logout_cleared": True,
    "javascript_errors": errors,
    "writes": 0,
    "protected_originals_verified": checked,
    "delivery": "disabled",
}
(ROOT / "reports/article-packet-runtime.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
