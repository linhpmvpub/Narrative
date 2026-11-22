"""Read-only live authoring UI plus intercepted synthetic review-form check."""

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
    page.goto("http://127.0.0.1:8888/news-review")
    page.locator("#token").fill(
        (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
    )
    page.locator("#login button").click()
    expect(page.locator("#workspace")).to_be_visible()
    page.locator("#load").click()
    expect(page.locator("#source")).not_to_have_value("")
    page.locator("#source").evaluate(
        '(n)=>{n.focus();n.setSelectionRange(0,n.value.indexOf("\\n"));}'
    )
    page.locator("#quote").click()
    body = json.loads(page.locator("#claim-json").input_value())
    assert body["source_span"]["start"] == 0 and body["claim_text"]
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#logout").click()
    expect(page.locator("#source")).to_have_value("")
    expect(page.locator("#claim-json")).to_have_value("")
    expect(page.locator("#claims")).to_be_empty()
    fake = {
        "items": [
            {
                "id": "synthetic-test",
                "author_id": "different-account",
                "payload": {
                    "ticker": "MU",
                    "claim": {"claim_text": "Synthetic Micron claim for browser test only"},
                },
                "status": "pending",
                "review_version": 0,
                "blocker": None,
            }
        ],
        "role": "admin",
        "current_user_id": "synthetic-operator",
    }
    page.route("**/api/v0/news-claims", lambda route: route.fulfill(json=fake))
    page.route(
        "**/api/v0/news-claims/synthetic-test/reviews",
        lambda route: route.fulfill(json={"decision": "rejected", "version": 1}),
    )
    page.locator("#token").fill(
        (ROOT / "secrets/development-operator-access-token.txt").read_text().strip()
    )
    page.locator("#login button").click()
    expect(page.locator("#claims form")).to_be_visible()
    page.locator("#claims select").nth(0).select_option("rejected")
    page.locator("#claims select").nth(1).select_option("AI_SIMULATED")
    page.locator("#claims textarea").fill(
        "Synthetic browser test; no real approval or claim created."
    )
    page.locator("#claims form button").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.request.get("http://127.0.0.1:8890/news-review").status == 404
    assert not errors, errors
    page.locator("#logout").click()
    expect(page.locator("#claims")).to_be_empty()
    browser.close()
(ROOT / "reports/news-claims-browser.json").write_text(
    json.dumps(
        {
            "checks": [
                "live_source_read",
                "exact_quote_offsets",
                "member_authoring_ui",
                "synthetic_intercepted_operator_review",
                "mobile_layout",
                "logout_clears",
                "gateway_review_blocked",
            ],
            "browser_errors": errors,
            "production_writes": 0,
        },
        indent=2,
    )
    + "\n"
)
print("Claim review browser checks passed; no production writes")
