"""Local browser integration for segment evidence; credentials stay on this machine."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8890/map")
    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )
    page.locator("#auth button").first.click()
    expect(page.locator("#eligible-count")).to_have_text("0")
    button = page.get_by_role(
        "button", name="InfrastructureSolutionsGroup · REVENUE", exact=False
    ).first
    button.wait_for()
    page.wait_for_function(
        "() => document.querySelector('#notice').textContent.includes('Kịch bản giả định đã tính')"
    )
    button.click()
    expect(page.locator("#detail")).to_contain_text("StatementBusinessSegmentsAxis")
    expect(page.locator("#detail")).to_contain_text("UNKNOWN")
    page.screenshot(path=str(ROOT / "reports/segments-map-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(ROOT / "reports/segments-map-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("button", name="Giải thích nguyên nhân · ISSUER_ATTRIBUTION").first.click()
    expect(page.locator("#detail")).to_contain_text("Chưa được xác minh")
    page.goto("http://127.0.0.1:8890/")
    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )
    page.locator("#login-form button").click()
    page.locator(".causal-evidence").first.wait_for()
    expect(page.locator("#entries")).to_contain_text("dell:InfrastructureSolutionsGroupMember")
    assert page.locator("#share").is_hidden()
    assert not errors, errors
    page.screenshot(path=str(ROOT / "reports/segments-feed-mobile.png"), full_page=True)
    browser.close()
(ROOT / "reports/segments-browser.json").write_text(
    json.dumps(
        {
            "errors": errors,
            "checks": [
                "segment_period_source_context_detail",
                "issuer_attribution_not_independent_cause",
                "no_verified_edges",
                "private_feed",
                "readonly_mobile",
                "no_horizontal_overflow",
            ],
            "delivery": "disabled",
        },
        indent=2,
    )
)
print("Segment browser checks passed")
