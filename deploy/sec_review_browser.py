"""Browser acceptance on fabricated filings; real 50-filing preview is read-only."""

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
scratch = ROOT / "source-cache" / ("browser-review-" + uuid4().hex)
scratch.mkdir(parents=True)
env = {
    **os.environ,
    "DATABASE_URL": "sqlite:///" + (scratch / "review.db").as_posix(),
    "REVIEW_BROWSER_FOLDER": str(scratch),
}
prepare = """
import json, os, sys
from pathlib import Path
from alembic import command
from alembic.config import Config
from engine.db import database
from engine.seed import seed
from engine.api.accounts import provision
from engine.sec_review import initialize_review_store, import_collection
sys.path.insert(0, 'tests')
from test_sec_review import collection
command.upgrade(Config('alembic.ini'), 'head')
db=database(); seed(db, Path('config')); initialize_review_store(db)
import_collection(db, collection(Path(os.environ['REVIEW_BROWSER_FOLDER'])))
author=provision(db,'browser-test',admin=True)[1]
reviewer=provision(db,'browser-test',admin=True)[1]
print(json.dumps({'author':author,'reviewer':reviewer}))
db.dispose()
"""
python = str(ROOT / ".venv/Scripts/python.exe")
credentials = json.loads(subprocess.check_output([python, "-c", prepare], cwd=ROOT, env=env))
server = subprocess.Popen(
    [
        python,
        "-m",
        "uvicorn",
        "engine.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8887",
        "--no-access-log",
    ],
    cwd=ROOT,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
errors = []
try:
    for _ in range(40):
        try:
            urllib.request.urlopen("http://127.0.0.1:8887/readyz", timeout=1).close()
            break
        except OSError:
            time.sleep(0.25)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("dialog", lambda dialog: dialog.accept())
        page.goto("http://127.0.0.1:8887/review")
        page.locator("#token").fill(credentials["author"])
        page.locator("#login-form button").click()
        expect(page.locator("#filings .filing")).to_have_count(1)
        page.locator("#filings .filing").click()
        expect(page.locator("#source-text")).to_have_value("Revenue increased.")
        form = page.locator("#draft-form")
        for name, value in {
            "headline": "TEST ONLY — fabricated filing",
            "event_type": "earnings",
            "published_at": "2026-11-01T10:00:00",
            "occurrence_window": "FY2026-Q3",
            "period": "FY2026-Q3",
            "comparison_basis": "qualitative; no numeric comparison",
            "quote": "Revenue increased.",
            "start": "0",
            "uncertainties": "Fabricated test text, not market facts",
        }.items():
            form.locator('[name="' + name + '"]').fill(value)
        form.locator("button").click()
        expect(page.locator("#history article")).to_have_count(1)
        page.locator("#disconnect").click()
        page.locator("#token").fill(credentials["reviewer"])
        page.locator("#login-form button").click()
        page.locator("#filings .filing").click()
        review = page.locator("#review-form")
        expect(review).to_be_visible()
        review.locator('[name="decision"]').select_option("approved")
        review.locator('[name="note"]').fill("Independent test-only review")
        review.locator('[name="rights_basis"]').fill("Fabricated text for automated testing only")
        for name in ("identity_confirmed", "citation_confirmed", "comparison_confirmed"):
            review.locator('[name="' + name + '"]').check()
        review.locator("button").click()
        expect(review).not_to_be_visible()
        expect(page.locator("#history")).to_contain_text("Đã duyệt · chưa xuất bản")
        assert page.evaluate("localStorage.length === 0 && sessionStorage.length === 0")
        page.locator("#disconnect").click()
        expect(page.locator("#source-text")).to_have_value("")
        # Read-only check of real local captures: do not author or approve market claims.
        page.goto("http://127.0.0.1:8886/review")
        page.locator("#token").fill((ROOT / "secrets/sec-review-access-token.txt").read_text())
        page.locator("#login-form button").click()
        expect(page.locator("#filings .filing")).to_have_count(50)
        page.locator("#filings .filing").first.click()
        expect(page.locator("#detail")).to_be_visible()
        page.screenshot(path=str(ROOT / "reports/sec-review-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(ROOT / "reports/sec-review-mobile.png"), full_page=True)
        page.locator("#disconnect").click()
        browser.close()
    assert not errors, errors
    (ROOT / "reports/sec-review-browser.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "test_data": "fabricated local filing",
                "checks": [
                    "draft saved",
                    "independent reviewer approval",
                    "logout clears source text",
                    "no browser credential persistence",
                    "50 real captures read-only",
                    "desktop/mobile layout",
                ],
                "real_filings_approved": 0,
                "javascript_errors": errors,
                "delivery": "disabled",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("SEC review browser acceptance passed; no real filing approved")
finally:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True)
    else:
        server.terminate()
    server.wait(timeout=15)
