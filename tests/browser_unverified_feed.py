"""Read-only gateway check for separately labeled financial extracts."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8890/news")
    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )
    page.locator("#connect button").click()
    expect(page.locator("#workspace")).to_be_visible()
    expect(page.locator("#extraction-list article")).to_have_count(2)
    expect(page.locator("#extraction-list")).to_contain_text("Bản trích chưa xác minh")
    expect(page.locator("#extraction-list")).to_contain_text("chưa xác minh")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.route(
        "**/api/v0/news/extractions", lambda route: route.fulfill(status=503, body="unavailable")
    )
    page.locator("#refresh").click()
    expect(page.locator("#extraction-list article")).to_have_count(0)
    expect(page.locator("#extraction-list")).to_contain_text("Đã ẩn")
    page.unroute("**/api/v0/news/extractions")
    page.locator("#refresh").click()
    expect(page.locator("#extraction-list article")).to_have_count(2)
    page.locator("#logout").click()
    expect(page.locator("#extraction-list")).to_be_empty()
    assert not errors
    browser.close()
report = {
    "gateway": True,
    "viewport_width": 390,
    "actual_unverified_cards": 2,
    "failure_withholds": True,
    "logout_clears": True,
    "overflow": False,
    "javascript_errors": errors,
    "writes": 0,
    "delivery": "disabled",
}
(ROOT / "reports/article-feed-browser.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
