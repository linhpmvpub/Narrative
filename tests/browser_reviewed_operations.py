"""Local UI smoke test with an explicitly synthetic in-browser response, no DB writes."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
token = (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
card = {"id": "synthetic-browser-only", "headline": "SYNTHETIC — operating context UI test",
    "ticker": "TEST", "narrative_title": "Synthetic product supply", "excerpt": "Our systems ramp increased.",
    "issuer": "TEST", "published_at": "2026-01-01T00:00:00Z", "version": 1,
    "reviewer_kind": "AI_INDEPENDENT", "roles": [], "links": [{"scope": "Synthetic scope only",
        "path": [{"from": "Product", "to": "Supply", "scope": "Synthetic path",
                  "evidence": [{"quote": "Synthetic profile evidence"}]}]}],
    "decision_trace": ["Cùng doanh nghiệp phát hành; cụm từ hoạt động và sản phẩm nằm trong một câu"],
    "profile_sources": [], "source_url": "https://example.test/synthetic"}
errors = []
expect.set_options(timeout=20000)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                                headless=True)
    for width in (390, 1440):
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8890/news")
        page.locator("#token").fill(token)
        page.locator("#connect button").click()
        root = page.locator("#reviewed-operation-list")
        expect(root).to_contain_text("Chưa có trích đoạn")
        page.route("**/api/v0/news/reviewed-operations", lambda r: r.fulfill(
            json={"items": [card], "delivery": "disabled", "graph_modified": False}))
        page.locator("#refresh").click()
        expect(root.locator("article")).to_have_count(1)
        expect(root).to_contain_text("SYNTHETIC")
        expect(root).to_contain_text("Kiểm duyệt AI độc lập")
        expect(root).to_contain_text("Thông báo thật tắt")
        root.locator("summary").click()
        expect(root).to_contain_text("Cùng doanh nghiệp")
        assert root.locator('a[href="https://example.test/synthetic"]').count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.unroute("**/api/v0/news/reviewed-operations")
        page.route("**/api/v0/news/reviewed-operations", lambda r: r.fulfill(status=503))
        page.locator("#refresh").click()
        expect(root.locator("article")).to_have_count(0)
        expect(root).to_contain_text("đã ẩn dữ liệu")
        page.unroute("**/api/v0/news/reviewed-operations")
        page.locator("#refresh").click()
        expect(root).to_contain_text("Chưa có trích đoạn")
        page.locator("#logout").click()
        expect(root).to_be_empty()
        page.close()
    browser.close()
assert not errors
result = {"widths": [390, 1440], "synthetic_response_only": True, "real_operating_cards": 0,
          "failure_hides": True, "recovery_restores_empty_state": True, "logout_clears": True,
          "overflow": False, "javascript_errors": errors, "database_writes": 0, "delivery": "disabled"}
(ROOT / "reports/reviewed-operations-browser.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
