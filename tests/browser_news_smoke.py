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

    page.locator("#logout").click()

    expect(page.locator("#news-list")).to_be_empty()
    expect(page.locator("#cluster-list")).to_be_empty()

    expect(page.locator("#workspace")).to_be_hidden()

    assert not errors, errors

    browser.close()

(ROOT / "reports/news-browser.json").write_text(
    json.dumps(
        {
            "visible_articles": count,
            "checks": [
                "authenticated_news",
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
