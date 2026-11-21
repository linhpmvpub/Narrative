import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
token = (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
report = {
    "browser_errors": [],
    "delivery": "disabled",
    "gateway": "loopback read-only; HTTPS email gate verified separately",
}
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    page.on("pageerror", lambda e: report["browser_errors"].append(str(e)))
    page.goto("http://127.0.0.1:8890/map")
    page.locator("#paths button").first.wait_for()
    page.locator("#token").fill(token)
    page.locator("#auth button").first.click()
    page.locator("#graph .reported").first.wait_for()
    assert page.locator("#graph .reported").count() == 4
    page.locator("#graph .reported").first.click()
    expect(page.locator("#detail")).to_contain_text("JSON pointer")
    expect(page.locator("#detail")).to_contain_text("USD")
    expect(page.locator("#detail")).to_contain_text("UNKNOWN")
    page.screenshot(path=str(ROOT / "reports/financial-map-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ROOT / "reports/financial-map-mobile.png"), full_page=True)
    page.goto("http://127.0.0.1:8890/")
    page.locator("#token").fill(token)
    page.locator("#login-form button").click()
    page.locator(".financial-comparisons").first.wait_for()
    assert page.locator(".financial-comparisons").count() >= 1
    assert page.locator("#add-open").is_hidden()
    assert page.locator("#share").is_hidden()
    assert page.locator(".card-actions").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ROOT / "reports/financial-feed-mobile.png"), full_page=True)
    report["checks"] = [
        "four_reported_metric_nodes",
        "source_period_unit_detail",
        "financial_feed_rendered",
        "mobile_read_only_controls",
        "no_horizontal_overflow",
    ]
    assert not report["browser_errors"], report
    browser.close()
(ROOT / "reports/financial-browser.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
