"""Read-only checks with the three prepared account slots; no real human submissions."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "secrets/annotation-campaign-204"
manifest = json.loads((DIRECTORY / "manifest.json").read_text())
pid = manifest["packet_id"]
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(20000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    for slot in ("reviewer_a", "reviewer_b"):
        credential = (DIRECTORY / (slot + ".txt")).read_text().strip()
        page.goto("http://127.0.0.1:8890/label")
        page.locator("#token").fill(credential)
        page.locator("#login button").click()
        expect(page.locator("#count")).to_contain_text("/204")
        page.locator("#cases button").first.click()
        expect(page.locator("#reason")).to_have_value("")
        assert not page.locator("#independent").is_checked()
        response = page.request.get(
            f"http://127.0.0.1:8888/api/v0/admin/evaluation/{pid}/quality",
            headers={"Authorization": "Bearer " + credential},
        )
        assert response.status == 403
        page.locator("#logout").click()
    credential = (DIRECTORY / "adjudicator.txt").read_text().strip()
    page.goto("http://127.0.0.1:8888/adjudicate")
    page.locator("#token").fill(credential)
    page.locator("#login button").click()
    expect(page.locator("#quality")).to_contain_text("408")
    expect(page.locator("#quality")).to_contain_text("reviewer_a: 0/204")
    expect(page.locator("#quality")).to_contain_text("reviewer_b: 0/204")
    expect(page.locator("#quality")).to_contain_text("AI MÔ PHỎNG")
    expect(page.locator("#quality")).to_contain_text("Nhà đầu tư cá nhân: 204/204")
    expect(page.locator("#quality")).to_contain_text("còn chờ: 0")
    expect(page.locator("#quality")).to_contain_text("cần làm 204")
    expect(page.locator("#count")).to_contain_text("0 / 204")
    page.screenshot(path=str(ROOT / "reports/campaign-progress-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / "reports/campaign-progress-mobile.png"), full_page=True)
    assert (
        page.request.get(
            f"http://127.0.0.1:8888/api/v0/admin/evaluation/{pid}/export",
            headers={"Authorization": "Bearer " + credential},
        ).status
        == 403
    )
    assert page.request.get("http://127.0.0.1:8890/adjudicate").status == 404
    page.locator("#logout").click()
    assert not errors, errors
    browser.close()
(ROOT / "reports/campaign-browser.json").write_text(
    json.dumps(
        {
            "reviewers_checked": 2,
            "cases_each": 204,
            "scoped_adjudicator_checked": True,
            "global_export_blocked": True,
            "gateway_unchanged": True,
            "real_labels_created": 0,
            "js_errors": errors,
            "mobile_overflow": False,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("Campaign browser checks passed; all real account checks read-only.")
