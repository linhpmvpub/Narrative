"""Read-only local checks of the privately reviewed historical accounting case."""

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
    page.on("pageerror", lambda error: errors.append(str(error)))
    token = (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    page.goto("http://127.0.0.1:8890/news")
    page.locator("#token").fill(token)
    page.locator("#connect button").click()
    expect(page.locator("#impact-case-list article")).to_have_count(1)
    expect(page.locator("#impact-case-list")).to_contain_text("10.21")
    page.locator("#impact-case-list summary").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.route("**/api/v0/news/impact-cases", lambda route: route.fulfill(status=503))
    page.locator("#refresh").click()
    expect(page.locator("#impact-case-list article")).to_have_count(0)
    expect(page.locator("#impact-case-list")).to_contain_text("đã ẩn dữ liệu")
    page.unroute("**/api/v0/news/impact-cases")
    page.locator("#refresh").click()
    expect(page.locator("#impact-case-list article")).to_have_count(1)
    page.locator("#logout").click()
    expect(page.locator("#impact-case-list")).to_be_empty()
    page.goto("http://127.0.0.1:8890/map")
    page.locator("#token").fill(token)
    page.locator("#auth button").first.click()
    expect(page.locator("#mode-badge")).to_contain_text("DỮ LIỆU THẬT")
    page.locator("#ticker").select_option("NVDA")
    page.locator("#load").click()
    expect(page.locator("#evidence")).to_contain_text("10.21")
    expect(page.locator("#eligible-count")).to_have_text("0")
    page.locator("#evidence summary").last.click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#asof").fill("2025-06-01T00:00")
    page.locator("#load").click()
    expect(page.locator("#evidence")).not_to_contain_text("10.21")
    page.locator("#logout").click()
    expect(page.locator("#mode-badge")).to_contain_text("DEMO")
    assert not errors
    browser.close()
report = {"local_gateway": True, "viewport_width": 390, "real_cases": 1,
          "failure_withholds": True, "cutoff_withholds": True, "logout_clears": True,
          "overflow": False, "javascript_errors": errors, "writes": 0,
          "delivery": "disabled"}
(ROOT / "reports/impact-case-browser.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
