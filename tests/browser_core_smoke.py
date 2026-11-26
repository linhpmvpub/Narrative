"""Local browser smoke with actual local projection and intercepted HTTP (no server/tunnel)."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from engine.core_workspace import build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parents[1] / "engine/web"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
        )
        page = browser.new_page(viewport={"width": 1365, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        pending = []
        delay = False
        unavailable = False

        def respond(route):
            url = route.request.url
            if "/api/v0/news/core" in url:
                assert route.request.headers["authorization"] == "Bearer synthetic-browser-token"
                if delay:
                    pending.append(route)
                    return
                if unavailable:
                    route.fulfill(status=503, body="Unavailable")
                    return
                payload = build(args.manifest, include_synthetic="=true" in url)
                route.fulfill(json=payload)
            elif "/assets/" in url:
                name = url.rsplit("/", 1)[1]
                route.fulfill(
                    path=assets / name,
                    content_type="text/javascript" if name.endswith(".js") else "text/css",
                )
            else:
                route.fulfill(path=assets / "core.html", content_type="text/html")

        page.route("http://127.0.0.1:18991/**", respond)
        page.goto("http://127.0.0.1:18991/core")
        page.locator("#token").fill("synthetic-browser-token")
        page.locator("#login button").click()
        page.locator("#profiles article").first.wait_for()
        assert page.locator("#profiles article").count() == 6
        assert page.locator("#paths article").count() == 7
        assert page.locator("#cards article").count() == 0
        assert page.locator("#token").input_value() == ""
        page.screenshot(path=args.output / "desktop.png", full_page=True)
        page.locator("#synthetic").check()
        page.locator("#cards article").first.wait_for()
        assert page.locator("#cards article").count() == 2
        page.locator("#company").select_option("AMD")
        assert page.locator("#cards article").count() == 1
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=args.output / "mobile.png", full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.evaluate("localStorage.length === 0 && sessionStorage.length === 0")
        page.locator("#logout").click()
        assert page.locator("#content").is_hidden()
        assert page.locator("#cards article").count() == 0
        page.locator("#token").fill("synthetic-browser-token")
        page.locator("#login button").click()
        page.locator("#profiles article").first.wait_for()
        unavailable = True
        page.locator("#refresh").click()
        page.wait_for_function("document.getElementById('status').textContent.includes('503')")
        assert page.locator("#profiles article").count() == 0
        unavailable = False
        delay = True
        page.locator("#refresh").click()
        page.wait_for_timeout(100)
        assert pending
        page.locator("#logout").click()
        pending.pop().fulfill(json=build(args.manifest))
        page.wait_for_timeout(100)
        assert page.locator("#content").is_hidden()
        assert page.locator("#profiles article").count() == 0
        assert not errors, errors
        browser.close()
    print(json.dumps({"desktop_mobile_auth_filter_logout": "passed", "page_errors": errors}))


if __name__ == "__main__":
    main()
