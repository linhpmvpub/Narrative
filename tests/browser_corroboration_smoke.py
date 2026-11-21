"""Inspect external source assessments on the private map without creating labels."""

import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    expect.set_options(timeout=20000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8890/map")
    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )
    page.locator("#auth button").first.click()
    page.wait_for_function(
        "() => state.graph && !state.graph.is_synthetic && document.querySelector('#notice').textContent.includes('Kịch bản giả định đã tính')"
    )
    assert page.evaluate("state.graph.edges.filter(e=>e.cross_source_assessment).length") == 8
    page.get_by_role("button", name=re.compile("^R028")).click()
    page.get_by_role("button", name="Xem đối chiếu nguồn độc lập").click()
    expect(page.locator("#detail")).to_contain_text("PEER_MECHANISM_ONLY")
    expect(page.locator("#detail")).to_contain_text("Hewlett Packard Enterprise")
    expect(page.locator("#eligible-count")).to_have_text("0")
    page.screenshot(path=str(ROOT / "reports/corroboration-map-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / "reports/corroboration-map-mobile.png"), full_page=True)
    assert not errors, errors
    browser.close()
(ROOT / "reports/corroboration-browser.json").write_text(
    json.dumps(
        {
            "checks": [
                "8_temporal_cross_source_assessments",
                "peer_independence_and_limits",
                "no_graph_approval",
                "mobile_layout",
            ],
            "browser_errors": errors,
            "delivery": "disabled",
        },
        indent=2,
    )
)
print("Cross-source browser checks passed")
