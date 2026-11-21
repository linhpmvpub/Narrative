"""Real assigned corpus read-only check; label writes use intercepted synthetic API only."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
credential = ROOT / "secrets/annotation-campaign-204/reviewer_a.txt"
if not credential.exists():
    credential = ROOT / "secrets/development-feed-access-token.txt"
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(20000)
    expect.set_options(timeout=20000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8890/label")
    page.locator("#token").fill(credential.read_text().strip())
    page.locator("#login button").click()
    expect(page.locator("#count")).to_contain_text("/204")
    page.locator("#kind").select_option("causal_language")
    page.locator("#cases button").first.click()
    page.locator("#language").wait_for()
    assert page.locator("#language").input_value() == ""
    assert page.locator("#reason").input_value() == ""
    assert not page.locator("#independent").is_checked()
    page.screenshot(path=str(ROOT / "reports/annotation-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / "reports/annotation-mobile.png"), full_page=True)
    page.locator("#kind").select_option("segment_comparison")
    page.locator("#cases button").first.click()
    page.locator("#verdict").wait_for()
    assert page.locator("#current_value").input_value() == ""
    page.screenshot(path=str(ROOT / "reports/annotation-numeric-mobile.png"), full_page=True)
    page.locator("#logout").click()
    # All following API reads/writes are synthetic browser fixtures, never sent to the server.
    pid = "a" * 64
    original = {
        "source_url": "https://example.org/synthetic-test",
        "source_sha256": "0" * 64,
        "snapshot_id": "fixture",
        "as_of": "2026-11-01T00:00:00Z",
        "available_at": "2026-10-01T00:00:00Z",
        "ticker": "DELL",
        "accession": "SYNTHETIC-ONLY",
    }
    cases = [
        {
            **original,
            "id": "b" * 64,
            "kind": "causal_language",
            "text": "Synthetic revenue increase due to fictional demand for testing only.",
        },
        {
            **original,
            "id": "c" * 64,
            "kind": "segment_comparison",
            "concept": "us-gaap:Revenues",
            "dimensions": [],
            "current_locator": "f1",
            "prior_locator": "f2",
        },
    ]
    saved = {}
    writes = []
    held = []
    hold = {"next": False}

    def respond(route):
        request = route.request
        path = request.url.split("/api/v0/annotations")[1].split("?")[0]
        if request.method == "POST":
            data = request.post_data_json
            cid = path.split("/")[3]
            assert "idempotency-key" in request.headers
            writes.append(data)
            saved[cid] = data
            route.fulfill(
                json={
                    "version": data["expected_version"] + 1,
                    "delivery": "disabled",
                    "graph_modified": False,
                }
            )
            return
        if path == "/packets":
            data = {"items": [{"id": pid, "case_count": 2}]}
        elif path.endswith("/cases"):
            data = {"items": [{**c, "my_version": 0} for c in cases], "next_offset": None}
        else:
            cid = path.rsplit("/", 1)[1]
            c = next(c for c in cases if c["id"] == cid)
            data = {
                "case": c,
                "my_label": saved.get(cid),
                "my_version": 1 if cid in saved else 0,
                "source_status": "CURRENT",
            }
            if hold["next"]:
                held.append((route, data))
                hold["next"] = False
                return
        route.fulfill(json=data)

    page.route("**/api/v0/annotations/**", respond)
    page.locator("#token").fill("synthetic-browser-token")
    page.locator("#login button").click()
    expect(page.locator("#count")).to_contain_text("/2")
    page.locator("#kind").select_option("causal_language")
    page.locator("#cases button").first.click()
    page.locator("#language").select_option("NO_CAUSAL_CLAIM")
    page.locator("#reason").fill("Synthetic independent human annotation for browser test only")
    page.locator("#independent").check()
    page.locator("#save").click()
    expect(page.locator("#notice")).to_contain_text("v1")
    assert len(writes) == 1 and writes[0]["language"] == "NO_CAUSAL_CLAIM"
    page.locator("#kind").select_option("segment_comparison")
    page.locator("#cases button").first.click()
    page.locator("#verdict").select_option("COMPARABLE")
    page.locator("#reason").fill("Synthetic numerical comparison, manually entered for UI test")
    page.locator("#independent").check()
    page.locator("#save").click()
    assert len(writes) == 1  # Browser blocks missing required independent operands.
    for key, value in {
        "current_value": "120",
        "prior_value": "100",
        "current_start": "2026-04-01",
        "current_end": "2026-06-30",
        "prior_start": "2025-04-01",
        "prior_end": "2025-06-30",
    }.items():
        page.locator("#" + key).fill(value)
    page.locator("#save").click()
    expect(page.locator("#notice")).to_contain_text("v1")
    assert len(writes) == 2 and writes[1]["numeric"]["current_value"] == "120"
    hold["next"] = True
    page.locator("#kind").select_option("causal_language")
    page.locator("#cases button").first.click()
    page.locator("#logout").click()
    assert held
    route, data = held.pop()
    route.fulfill(json=data)
    expect(page.locator("#workspace")).to_be_hidden()
    expect(page.locator("#detail")).to_be_empty()
    assert not errors, errors
    browser.close()
report = {
    "checks": [
        "204_assigned_cases",
        "no_prefilled_predictions",
        "language_and_numeric_forms",
        "synthetic_writes_only",
        "required_operands",
        "late_private_response_after_logout_ignored",
        "mobile_layout",
    ],
    "browser_errors": errors,
    "real_labels_created": 0,
    "delivery": "disabled",
}
(ROOT / "reports/annotation-browser.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report))
