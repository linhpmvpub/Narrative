"""Read-only real local profile/card smoke; no source or subscription writes."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    token = (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    for width in (390, 1440):
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8890/news")
        page.locator("#token").fill(token)
        page.locator("#connect button").click()
        expect(page.locator("#profile-list article")).to_have_count(1)
        expect(page.locator("#profile-list")).to_contain_text("6/42")
        expect(page.locator("#profile-list")).to_contain_text("MẪU LỊCH SỬ")
        expect(page.locator("#profile-list")).to_contain_text("Thách thức giả định")
        expect(page.locator("#profile-list article ol li")).to_have_count(3)
        page.locator("#profile-list > details > summary").click()
        page.locator("#profile-list article summary").click()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator("#profile-list article a").first.get_attribute("href").startswith(
            "https://www.sec.gov/Archives/"
        )
        page.route("**/api/v0/news/profiles", lambda route: route.fulfill(status=503))
        page.locator("#refresh").click()
        expect(page.locator("#profile-list")).to_contain_text("đã ẩn dữ liệu")
        expect(page.locator("#profile-list article")).to_have_count(0)
        page.unroute("**/api/v0/news/profiles")
        page.locator("#refresh").click()
        expect(page.locator("#profile-list article")).to_have_count(1)
        page.locator("#logout").click()
        expect(page.locator("#profile-list")).to_be_empty()
        page.close()
    assert not errors
    browser.close()
report = {"local_gateway": True, "widths": [390, 1440], "real_historical_cards": 1,
          "component_coverage_visible": True, "path_edges": 3, "source_link": True,
          "failure_withholds": True, "recovery_restores": True, "logout_clears": True,
          "overflow": False, "javascript_errors": errors, "writes": 0, "delivery": "disabled"}
(ROOT / "reports/company-profiles-browser.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
