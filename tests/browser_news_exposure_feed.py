"""Read-only live map plus intercepted synthetic baseline shares; no DB writes."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
operand = {
    "current": {"start": "2026-07-01", "end": "2026-09-30", "value": "25"},
    "unit": "USD",
    "filing_url": "https://www.sec.gov/synthetic-only",
    "source_sha256": "a" * 64,
    "snapshot_id": "synthetic-source",
}
share = {
    "ticker": "MU",
    "segment": "Synthetic memory segment",
    "percent": "25.0000",
    "numerator": operand,
    "denominator": {**operand, "current": {**operand["current"], "value": "100"}},
    "reviewed_at": "2026-11-22T10:00:00Z",
    "reviewer_kind": "AI_SIMULATED",
    "pair_sha256": "b" * 64,
}
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8888/map")
    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )
    page.locator("#auth button").first.click()
    expect(page.locator("#mode-badge")).to_contain_text("DỮ LIỆU THẬT")
    page.wait_for_function("() => document.querySelector('#path-count').textContent==='0'")
    graph = page.evaluate("state.graph")
    graph["baseline_exposure"] = {"items": [share], "truncated": False}
    page.route("**/api/v0/impact-map?*", lambda route: route.fulfill(json=graph))
    page.locator("#ticker").select_option("MU")
    page.locator("#load").click()
    expect(page.locator("#evidence")).to_contain_text("tỷ trọng doanh thu nền 25.0000%")
    expect(page.locator("#evidence progress")).to_have_attribute("value", "25")
    page.get_by_role("button", name="Xem nguồn tỷ trọng nền").click()
    expect(page.locator("#detail")).to_contain_text("UNKNOWN")
    expect(page.locator("#eligible-count")).to_have_text("0")
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    graph["baseline_exposure"]["items"] = []
    page.evaluate("refreshBaselineShares()")
    expect(page.locator("#evidence progress")).to_have_count(0)
    expect(page.locator("#detail")).not_to_contain_text("Synthetic memory segment")
    page.locator("#logout").click()
    expect(page.locator("#mode-badge")).to_contain_text("DEMO")
    page.goto("http://127.0.0.1:8890/news")
    item = {
        "headline": "Synthetic baseline news",
        "excerpt": "Synthetic source only",
        "version": 1,
        "published_at": "2026-11-22T08:00:00Z",
        "captured_at": "2026-11-22T09:00:00Z",
        "available_at": "2026-11-22T10:00:00Z",
        "author_kind": "AI_SIMULATED",
        "reviewer_kind": "AI_SIMULATED",
        "measurement": {"new_value": None},
        "source_url": "https://example.com/synthetic",
        "baseline_shares": [share],
    }
    page.route(
        "**/api/v0/news/reviewed*",
        lambda route: route.fulfill(
            json={
                "enabled": True,
                "items": [item],
                "as_of": "2026-11-22T10:00:00Z",
                "withheld_count": 0,
                "truncated": False,
            }
        ),
    )
    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )
    page.locator("#connect button").click()
    expect(page.locator("#reviewed-list")).to_contain_text("tỷ trọng doanh thu nền 25.0000%")
    page.locator("#reviewed-list summary").click()
    expect(page.locator("#reviewed-list")).to_contain_text("25 / 100 USD")
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    page.locator("#logout").click()
    expect(page.locator("#reviewed-list")).to_be_empty()
    assert not errors, errors
    browser.close()
(ROOT / "reports/news-exposure-feed-browser.json").write_text(
    json.dumps(
        {
            "checks": [
                "map_baseline_meter",
                "provenance_detail",
                "no_causal_edge",
                "revocation_refresh_clears",
                "feed_share_details",
                "mobile_no_overflow",
                "logout_clears",
            ],
            "browser_errors": errors,
            "production_writes": 0,
        },
        indent=2,
    )
    + "\n"
)
print("Baseline share browser checks passed; no production writes")
