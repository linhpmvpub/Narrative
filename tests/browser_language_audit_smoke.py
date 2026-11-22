"""Read-only inspection of post-hoc shadow diagnostics on the actual local packet."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(20000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8888/adjudicate")
    page.locator("#token").fill(
        (ROOT / "secrets/annotation-campaign-204/adjudicator.txt").read_text().strip()
    )
    page.locator("#login button").click()
    expect(page.locator("#quality")).to_contain_text("PHÂN TÍCH HỒI CỨU")
    expect(page.locator("#quality")).to_contain_text(
        "bản cũ 34/60, bản thử nghiệm 57/60; 1 ca giảm"
    )
    expect(page.locator("#quality")).to_contain_text("chỉ 53 đoạn văn")
    expect(page.locator("#quality")).to_contain_text("CHƯA ÁP DỤNG VÀO FEED")
    page.screenshot(path=str(ROOT / "reports/language-audit-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / "reports/language-audit-mobile.png"), full_page=True)
    assert page.request.get("http://127.0.0.1:8890/adjudicate").status == 404
    page.locator("#logout").click()
    expect(page.locator("#quality")).to_be_empty()
    assert not errors, errors
    browser.close()
(ROOT / "reports/language-audit-browser.json").write_text(
    json.dumps(
        {
            "checks": [
                "shadow_only_notice",
                "baseline_vs_candidate_counts",
                "regression_count",
                "deduplicated_denominator",
                "mobile_layout",
                "gateway_admin_blocked",
                "logout_clears_private_report",
            ],
            "browser_errors": errors,
            "writes": 0,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("Language audit browser checks passed; read-only, no label/graph mutations.")
