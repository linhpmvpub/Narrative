"""Actual pending corpus read-only; all adjudication writes intercepted synthetic fixtures."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
credential = ROOT / "secrets/annotation-campaign-204/adjudicator.txt"
if not credential.exists():
    credential = ROOT / "secrets/development-operator-access-token.txt"
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(20000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8888/adjudicate")
    page.locator("#token").fill(credential.read_text().strip())
    page.locator("#login button").click()
    expect(page.locator("#quality")).to_contain_text("204")
    expect(page.locator("#quality")).to_contain_text("PENDING_LABELS")
    expect(page.locator("#count")).to_contain_text("0 / 204")
    page.screenshot(path=str(ROOT / "reports/adjudication-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / "reports/adjudication-mobile.png"), full_page=True)
    assert page.request.get("http://127.0.0.1:8890/adjudicate").status == 404
    assert page.request.get("http://127.0.0.1:8890/api/v0/admin/evaluation/packets").status == 404
    page.locator("#logout").click()
    pid, cid = "a" * 64, "b" * 64
    saved, held = [], []
    control = {"hold": False, "numeric": False}

    def respond(route):
        path = route.request.url.split("/api/v0/admin/evaluation")[1]
        if route.request.method == "POST":
            saved.append(route.request.post_data_json)
            route.fulfill(
                json={"version": len(saved), "delivery": "disabled", "graph_modified": False}
            )
        elif path == "/packets":
            route.fulfill(json={"items": [{"id": pid, "case_count": 1}]})
        elif path.endswith("/quality"):
            route.fulfill(
                json={
                    "total_cases": 1,
                    "gold_cases": 0,
                    "status": "SYNTHETIC_TEST_ONLY",
                    "holdout": {},
                    "agreement": {},
                    "limitations": [],
                }
            )
        elif path.endswith("/cases"):
            route.fulfill(
                json={
                    "items": [
                        {
                            "id": cid,
                            "ticker": "DELL",
                            "kind": "causal_language",
                            "status": "DISAGREEMENT",
                            "vote_count": 2,
                        }
                    ]
                }
            )
        else:
            data = {
                "case": {
                    "id": cid,
                    "ticker": "DELL",
                    "kind": "segment_comparison" if control["numeric"] else "causal_language",
                    "source_url": "https://example.org/synthetic",
                    "text": "SYNTHETIC TEST ONLY: conflicting interpretations",
                },
                "status": "DISAGREEMENT",
                "votes": [
                    {
                        "user_id": "synthetic-A",
                        "version": 1,
                        "payload": {
                            "language": "NO_CAUSAL_CLAIM",
                            "reason": "Synthetic reviewer A",
                        },
                    },
                    {
                        "user_id": "synthetic-B",
                        "version": 1,
                        "payload": {
                            "language": "ISSUER_ATTRIBUTION",
                            "reason": "Synthetic reviewer B",
                        },
                    },
                ],
                "decision": None,
                "self_review_forbidden": False,
                "decision_version": len(saved),
                "vote_hash": "c" * 64,
            }
            if control["hold"]:
                held.append((route, data))
            else:
                route.fulfill(json=data)

    page.route("**/api/v0/admin/evaluation/**", respond)
    page.locator("#token").fill("synthetic-operator-not-real")
    page.locator("#login button").click()
    page.locator("#cases button").click()
    expect(page.locator("#decision-form")).to_be_visible()
    assert page.locator("#language").input_value() == ""
    assert not page.locator("#independent").is_checked()
    page.locator("#language").select_option("NO_CAUSAL_CLAIM")
    page.locator("#reason").fill("Synthetic independent resolution rationale")
    page.locator("#independent").check()
    page.locator("#save").click()
    expect(page.locator("#notice")).to_contain_text("Thông báo thật: tắt")
    expect(page.locator("#reason")).to_have_value("")
    assert (
        saved[-1]["expected_vote_hash"] == "c" * 64 and saved[-1]["language"] == "NO_CAUSAL_CLAIM"
    )
    page.locator("#outcome").select_option("DEFERRED")
    page.locator("#reason").fill("Synthetic evidence insufficient; defer decision")
    page.locator("#independent").check()
    page.locator("#save").click()
    expect(page.locator("#reason")).to_have_value("")
    assert saved[-1]["outcome"] == "DEFERRED" and "language" not in saved[-1]
    control["numeric"] = True
    page.locator("#cases button").click()
    expect(page.locator("#numeric-fields")).to_be_visible()
    page.locator("#verdict").select_option("COMPARABLE")
    page.locator("#reason").fill("Synthetic numeric independent resolution")
    page.locator("#independent").check()
    page.locator("#save").click()
    assert len(saved) == 2
    for side, year in [("current", 2026), ("prior", 2025)]:
        page.locator("#" + side + "_value").fill("120" if year == 2026 else "100")
        page.locator("#" + side + "_start").fill(f"{year}-04-01")
        page.locator("#" + side + "_end").fill(f"{year}-06-30")
    page.locator("#save").click()
    expect(page.locator("#reason")).to_have_value("")
    assert len(saved) == 3 and saved[-1]["numeric"]["prior_value"] == "100"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(
        path=str(ROOT / "reports/adjudication-synthetic-resolution.png"), full_page=True
    )
    control["hold"] = True
    page.locator("#cases button").click()
    page.wait_for_timeout(100)
    page.locator("#logout").click()
    for route, data in held:
        route.fulfill(json=data)
    expect(page.locator("#workspace")).to_be_hidden()
    expect(page.locator("#detail")).to_be_empty()
    assert not errors, errors
    browser.close()
(ROOT / "reports/adjudication-browser.json").write_text(
    json.dumps(
        {
            "actual_cases": 204,
            "actual_labels_created": 0,
            "actual_decisions_created": 0,
            "synthetic_intercepted_writes": len(saved),
            "gateway_admin_blocked": True,
            "mobile_overflow": False,
            "js_errors": errors,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(
    "Adjudication browser checks passed; actual corpus read-only, 3 synthetic writes intercepted."
)
