"""Local browser acceptance; run with Playwright installed in the audit environment."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
errors = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text)
            if message.type == "error" and "favicon" not in message.text
            else None
        ),
    )
    page.goto("http://127.0.0.1:8876/")
    page.locator("#demo").click()
    expect(page.locator("#entries article")).to_have_count(1)
    expect(page.locator("#demo-banner")).to_be_visible()
    expect(page.locator("#add-open")).to_be_disabled()
    page.screenshot(path=str(ROOT / "reports/ui-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / "reports/ui-mobile.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1100})
    page.locator("#logout").click()
    page.locator("#token").fill((ROOT / "secrets/local-access-token.txt").read_text())
    page.locator("#login-form button").click()
    expect(page.locator("#mode")).to_have_text("Riêng tư")
    expect(page.locator("#token")).to_have_value("")
    assert page.evaluate("localStorage.length === 0 && sessionStorage.length === 0")
    page.locator("#add-open").click()
    page.locator("#target").select_option("CO_DELL")
    page.locator("#subscribe-form button.primary").click()
    expect(page.locator("#threads .thread")).to_have_count(1)
    page.locator("#nav-narratives").click()
    page.locator("#create-open").click()
    form = page.locator("#narrative-form")
    for name, value in {
        "title": "Kiểm tra luận điểm riêng tư",
        "thesis": "Chi phí NAND có thể gây áp lực lên biên lợi nhuận.",
        "supporting_evidence": "Giá đầu vào tăng, chưa được bù trừ.",
        "challenging_evidence": "Tăng giá bán bù chi phí đầu vào.",
        "disconfirmation": "Biên lợi nhuận không giảm khi chi phí tăng.",
    }.items():
        form.locator('[name="' + name + '"]').fill(value)
    page.locator("#n-ticker").select_option("DELL")
    page.locator("#drivers").select_option("NAND_ASP")
    page.locator("#direction").select_option("-1")
    form.locator('[name="hypothesis_polarity"]').select_option("adverse")
    form.locator("button.primary").click()
    expect(page.locator("#create-dialog")).not_to_be_visible()
    expect(page.locator("#drafts article")).to_have_count(1)
    page.on("dialog", lambda dialog: dialog.accept())
    page.locator("#drafts button").click()
    expect(page.locator("#drafts .badge")).to_have_text("ĐÃ XÁC NHẬN")
    page.locator("#drafts button").click()
    expect(page.locator("#threads .thread")).to_have_count(2)
    page.locator("#logout").click()
    expect(page.locator("#workspace")).not_to_be_visible()
    expect(page.locator("#entries article")).to_have_count(0)
    browser.close()
assert not errors, errors
(ROOT / "reports/browser-smoke.json").write_text(
    json.dumps(
        {
            "status": "passed",
            "browser": "Chrome / Playwright",
            "live_notifications": False,
            "checks": [
                "synthetic demo",
                "desktop/mobile layout",
                "memory-only authentication",
                "stock subscription",
                "custom narrative draft/approval/subscription",
                "logout",
            ],
            "javascript_errors": errors,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("Browser acceptance passed")
