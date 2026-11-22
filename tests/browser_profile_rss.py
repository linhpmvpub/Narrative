"""Read-only local RSS-to-narrative browser smoke. Run while fixture news is fresh."""

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
errors = []
expect.set_options(timeout=20000)
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
    token = (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    request = urllib.request.Request("http://127.0.0.1:8890/api/v0/news/profile-rss",
                                     headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(request) as response:
        expected_cards = len(json.load(response)["items"])
    assert expected_cards >= 1
    for width in (390, 1440):
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8890/news")
        page.locator("#token").fill(token)
        page.locator("#connect button").click()
        root = page.locator("#rss-profile-list")
        expect(root.locator("article")).to_have_count(expected_cards)
        expect(root).to_contain_text("RSS CHƯA XÁC MINH")
        expect(root).to_contain_text("2 mục RSS cùng bài đã gộp")
        expect(root).to_contain_text("Bản chụp RSS gốc")
        expect(root).to_contain_text("Thông báo thật tắt")
        for summary in root.locator("summary").all():
            summary.click()
        assert root.locator('a[href^="https://www.sec.gov/Archives/"]').count() > 0
        assert root.locator("blockquote").count() > 0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.route("**/api/v0/news/profile-rss", lambda route: route.fulfill(status=503))
        page.locator("#refresh").click()
        expect(root.locator("article")).to_have_count(0)
        expect(root).to_contain_text("đã ẩn dữ liệu")
        page.unroute("**/api/v0/news/profile-rss")
        page.locator("#refresh").click()
        expect(root.locator("article")).to_have_count(expected_cards)
        page.locator("#logout").click()
        expect(root).to_be_empty()
        page.close()
    assert not errors
    browser.close()
report = {"widths": [390, 1440], "cards": expected_cards,
          "unverified_and_missing_capture_disclosed": True, "source_links": True,
          "failure_withholds": True, "recovery_restores": True, "logout_clears": True,
          "overflow": False, "javascript_errors": errors, "writes": 0, "delivery": "disabled"}
(ROOT / "reports/profile-rss-browser.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
