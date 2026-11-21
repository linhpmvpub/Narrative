"""Read-only browser verification against the local development preview."""

import json
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8888"
token = (ROOT / "secrets/development-feed-access-token.txt").read_text().strip()
report = {"base_url": BASE, "browser_errors": [], "checks": [], "delivery": "disabled"}
for attempt in range(20):
    try:
        with urlopen(BASE + "/readyz", timeout=2) as response:
            assert json.load(response)["schema"] == "0008"
        break
    except URLError:
        if attempt == 19:
            raise
        time.sleep(0.25)
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
    )
    page = browser.new_page(viewport={"width": 1600, "height": 1100})
    page.on("pageerror", lambda e: report["browser_errors"].append(str(e)))
    page.goto(BASE + "/map")
    page.locator("#paths button").first.wait_for()
    assert "CONDITIONAL_DECREASE" in page.locator("#paths").inner_text()
    assert page.locator("#graph .chosen").count() == 2
    before = page.locator("#graph").get_attribute("viewBox")
    page.locator("#zoom-in").click()
    assert page.locator("#graph").get_attribute("viewBox") != before
    page.locator("#fit").click()
    page.locator("#direction").select_option("-1")
    page.locator("#simulate").click()
    page.wait_for_function(
        "() => document.querySelector('#paths').textContent.includes('CONDITIONAL_INCREASE')"
    )
    page.locator("#sample").click()
    page.wait_for_function(
        "() => document.querySelector('#paths').textContent.includes('CONDITIONAL_DECREASE')"
    )
    page.screenshot(path=str(ROOT / "reports/impact-map-desktop.png"), full_page=True)
    report["checks"].extend(
        ["demo_uses_two_hop_path", "direction_reversal", "zoom", "F021_N08_trace"]
    )
    page.locator("#token").fill(token)
    page.locator("#auth button").first.click()
    page.wait_for_function(
        "() => document.querySelector('#mode-badge').textContent.includes('DỮ LIỆU THẬT')"
    )
    page.wait_for_function("() => document.querySelector('#path-count').textContent==='0'")
    assert page.locator("#evidence article").count() > 0
    assert page.locator("#eligible-count").inner_text() == "0"
    page.screenshot(path=str(ROOT / "reports/impact-map-private.png"), full_page=True)
    report["checks"].append("private_real_notices_no_fabricated_impact")
    page.locator("#logout").click()
    page.wait_for_function(
        "() => document.querySelector('#mode-badge').textContent.includes('DEMO')"
    )
    # Delay a private request, then logout. Its late response must never restore private UI.
    page.evaluate("""() => { const original=window.fetch; window.fetch=(url,...args)=>
      String(url).startsWith('/api/v0/impact-map?') ? new Promise(resolve=>{
        window.releasePrivate=()=>resolve(new Response(JSON.stringify({is_synthetic:false,nodes:[],edges:[],notices:[{ticker:'DELL',headline:'PRIVATE_RACE_SENTINEL',source_status:'active',version:1,url:'https://www.sec.gov/'}]}),{status:200,headers:{'Content-Type':'application/json'}}));
      }) : original(url,...args); }""")
    page.locator("#token").fill(token)
    page.locator("#auth button").first.click()
    page.wait_for_function('() => typeof window.releasePrivate === "function"')
    page.locator("#logout").click()
    page.wait_for_function(
        "() => document.querySelector('#mode-badge').textContent.includes('DEMO') && document.querySelector('#paths button')"
    )
    page.evaluate("window.releasePrivate()")
    page.wait_for_timeout(200)
    assert "PRIVATE_RACE_SENTINEL" not in page.locator("body").inner_text()
    assert "DEMO" in page.locator("#mode-badge").inner_text()
    assert page.evaluate("localStorage.length===0 && sessionStorage.length===0")
    report["checks"].append("late_private_response_ignored_after_logout")
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(ROOT / "reports/impact-map-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    report["checks"].append("mobile_no_horizontal_overflow")
    assert not report["browser_errors"], report
    browser.close()
(ROOT / "reports/impact-map-browser.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report))
