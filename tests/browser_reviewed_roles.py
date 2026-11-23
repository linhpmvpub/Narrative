"""Read-only local browser check; requires the reviewed historical SEC pilot."""

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
expect.set_options(timeout=20000)
token = (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
request = urllib.request.Request("http://127.0.0.1:8890/api/v0/news/reviewed-roles",
                                 headers={"Authorization": "Bearer " + token})
with urllib.request.urlopen(request) as response:
    result = json.load(response)
assert result["delivery"] == "disabled" and result["graph_modified"] is False
assert result["items"] and all(x["reviewer_kind"] == "AI_INDEPENDENT" for x in result["items"])
count = len(result["items"])
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
    for width in (390, 1440):
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8890/news")
        page.locator("#token").fill(token)
        page.locator("#connect button").click()
        root = page.locator("#reviewed-role-list")
        expect(root.locator("article")).to_have_count(count)
        expect(root).to_contain_text("Kiểm duyệt AI độc lập")
        expect(root).to_contain_text("Bên mua theo nguồn")
        expect(root).to_contain_text("Thông báo thật tắt")
        for summary in root.locator("summary").all():
            summary.click()
        expect(root).to_contain_text("phiên bản sự kiện mới nhất")
        assert root.locator('a[href^="https://www.sec.gov/Archives/"]').count() > 0
        assert root.locator("blockquote").count() > 0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.route("**/api/v0/news/reviewed-roles", lambda r: r.fulfill(status=503))
        page.locator("#refresh").click()
        expect(root.locator("article")).to_have_count(0)
        expect(root).to_contain_text("đã ẩn dữ liệu")
        page.unroute("**/api/v0/news/reviewed-roles")
        page.locator("#refresh").click()
        expect(root.locator("article")).to_have_count(count)
        page.locator("#logout").click()
        expect(root).to_be_empty()
        page.close()
    browser.close()
assert not errors
report = {"widths": [390, 1440], "reviewed_role_cards": count,
          "ai_review_disclosed": True, "source_quotes_and_paths": True,
          "failure_hides": True, "recovery_restores": True, "logout_clears": True,
          "overflow": False, "javascript_errors": errors, "browser_writes": 0,
          "delivery": "disabled", "graph_modified": False}
(ROOT / "reports/reviewed-role-browser.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
