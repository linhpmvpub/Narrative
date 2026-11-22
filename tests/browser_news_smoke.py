"""Read-only live preview checks; no source text or credentials in committed screenshots."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )

    page = browser.new_page(viewport={"width": 1440, "height": 950})

    errors = []

    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto("http://127.0.0.1:8890/news")

    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )

    page.locator("#connect button").click()

    expect(page.locator("#workspace")).to_be_visible()

    expect(page.locator("#news-list .news-card").first).to_be_visible()

    count = page.locator("#news-list .news-card").count()

    assert count > 0
    page.locator("#cluster-panel > summary").click()
    expect(page.locator("#cluster-list")).to_contain_text("nhóm ứng viên")
    expect(page.locator("#cluster-list")).to_contain_text("Chưa chuyển sang Impact Engine")
    page.locator("#cluster-panel > summary").click()

    assert page.locator("#token").input_value() == ""

    page.locator("#source").select_option("fed")

    expect(page.locator("#news-list .news-card").first).to_contain_text("Federal Reserve")

    page.set_viewport_size({"width": 390, "height": 844})

    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    # Keep live screenshots private; public report contains counts/checks only.

    page.screenshot(path=str(ROOT / "source-cache/news-mobile.png"), full_page=False)

    assert page.request.get("http://127.0.0.1:8890/adjudicate").status == 404

    # Intercepted presentation only; no production claim or event writes.
    fake_card = {
        "headline": "Synthetic reviewed Micron event",
        "excerpt": "<script>synthetic only</script>",
        "version": 2,
        "published_at": "2026-11-22T08:00:00Z",
        "captured_at": "2026-11-22T09:00:00Z",
        "available_at": "2026-11-22T10:00:00Z",
        "author_kind": "AI_SIMULATED",
        "reviewer_kind": "AI_SIMULATED",
        "measurement": {"new_value": None},
        "source_url": "https://example.com/synthetic",
    }
    reviewed = {
        "enabled": True,
        "items": [fake_card],
        "as_of": "2026-11-22T10:01:00Z",
        "withheld_count": 0,
        "truncated": False,
    }
    page.route("**/api/v0/news/reviewed*", lambda route: route.fulfill(json=reviewed))
    page.locator("#refresh").click()
    expect(page.locator("#reviewed-list")).to_contain_text("Synthetic reviewed Micron event")
    expect(page.locator("#reviewed-list")).to_contain_text("Agent AI")
    expect(page.locator("#reviewed-list")).to_contain_text("Bản 2")
    expect(page.locator("#reviewed-list script")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    reviewed["items"] = []
    reviewed["withheld_count"] = 1
    page.locator("#refresh").click()
    expect(page.locator("#reviewed-list .news-card")).to_have_count(0)
    expect(page.locator("#reviewed-list")).to_contain_text("1 sự kiện không còn đủ điều kiện")
    page.unroute("**/api/v0/news/reviewed*")
    page.route(
        "**/api/v0/news/reviewed*",
        lambda route: route.fulfill(status=503, json={"message": "test unavailable"}),
    )
    page.locator("#refresh").click()
    expect(page.locator("#reviewed-list")).to_contain_text("Đã ẩn sự kiện")
    expect(page.locator("#news-list .news-card").first).to_be_visible()
    page.locator("#logout").click()

    expect(page.locator("#news-list")).to_be_empty()
    expect(page.locator("#cluster-list")).to_be_empty()
    expect(page.locator("#reviewed-list")).to_be_empty()

    expect(page.locator("#workspace")).to_be_hidden()

    assert not errors, errors

    browser.close()

(ROOT / "reports/news-browser.json").write_text(
    json.dumps(
        {
            "visible_articles": count,
            "checks": [
                "authenticated_news",
                "reviewed_card_provenance_and_correction",
                "withdrawn_card_removed",
                "reviewed_endpoint_failure_clears_cards",
                "source_text_not_html",
                "source_filter",
                "candidate_clusters_and_impact_blockers",
                "mobile_no_overflow",
                "token_not_persisted",
                "logout_clears_content",
                "gateway_admin_blocked",
            ],
            "browser_errors": errors,
            "writes": 0,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

print("News desktop/mobile browser checks passed")
