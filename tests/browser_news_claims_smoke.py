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
    # Every mutation below is intercepted; never create a production claim or event.
    fake["items"][0]["status"] = "approved"
    fake["items"][0]["review_version"] = 1
    page.route(
        "**/api/v0/news-claims/synthetic-test/prepare",
        lambda route: route.fulfill(json={"payload_sha256": "a" * 64, "payload": {}}),
    )
    writes = []

    def intercepted_ingest(route):
        writes.append(route.request.post_data_json)
        if len(writes) == 3:
            route.fulfill(status=409, json={"message": "Source revision changed; prepare again"})
        else:
            route.fulfill(json={"action": writes[-1]["action"], "event_id": "synthetic-only"})

    page.route("**/api/v0/news-claims/synthetic-test/ingest", intercepted_ingest)
    page.route(
        "**/api/v0/news-claims/canonical*",
        lambda route: route.fulfill(
            json={
                "items": [],
                "withheld": [],
                "delivery": "disabled",
                "as_of": "2026-11-22T10:00:00Z",
            }
        ),
    )
    page.locator("#reload").click()
    for action in ["new", "duplicate", "correction"]:
        page.get_by_role("button", name="Chuẩn bị intake (chưa tạo sự kiện)").click()
        form = page.locator(".canonical-form")
        expect(form).to_be_visible()
        form.locator('[name="action"]').select_option(action)
        if action != "new":
            form.locator('[name="target_id"]').fill("synthetic-primary-claim")
        else:
            expect(form.locator('[name="target_id"]')).to_be_disabled()
        form.locator('[name="occurrence_window"]').fill("synthetic occurrence for UI test")
        form.locator('[name="identity_note"]').fill(
            "Synthetic operator identity confirmation; no real write"
        )
        form.locator('[name="identity_confirmed"]').check()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        form.get_by_role("button", name="Ghi canonical").click()
        if action != "correction":
            expect(page.locator("#result")).to_contain_text("synthetic-only")
        else:
            expect(page.locator("#notice")).to_contain_text("Source revision changed")
    assert [w["action"] for w in writes] == ["new", "duplicate", "correction"]
    assert all(w["expected_intake_sha256"] == "a" * 64 and w["identity_confirmed"] for w in writes)
    assert writes[0]["target_claim_id"] is None
    assert writes[1]["target_claim_id"] == "synthetic-primary-claim"
    page.locator("#snapshot-at").fill("2026-11-22T10:00:00Z")
    page.get_by_role("button", name="Đọc snapshot").click()
    expect(page.locator("#snapshot-result")).to_contain_text("2026-11-22T10:00:00Z")
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
                "canonical_new_duplicate_correction_intercepted",
                "stale_ingestion_error",
                "historical_snapshot_intercepted",
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
