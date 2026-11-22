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
selected = next(
    x for x in items if "NVDA" in x.get("ticker_mentions", []) and "nvidia" in x["title"].lower()
)
src = get("/api/v0/news-claims/source/" + selected["id"])
dossier = get(
    "/api/v0/news-claims/source/"
    + selected["id"]
    + "/dossier?"
    + urllib.parse.urlencode({"ticker": "NVDA", "expected_payload_sha256": src["payload_sha256"]})
)
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
    "real_dossier_evidence": dossier["raw_source_evidence"],
    "mobile_width": 390,
    "overflow": False,
    "logout_cleared": True,
    "javascript_errors": errors,
    "writes": 0,
    "protected_originals_verified": checked,
    "delivery": "disabled",
}
(ROOT / "reports/news-evidence-runtime.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
