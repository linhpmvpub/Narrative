# Release v0 — standalone product update

**NO_GO for production; validated for isolated synthetic/private development.** The user removed the Threadnote dependency. Narrative now has its own Vietnamese interface. Live notifications and LLM execution remain disabled.

| Gate | Current evidence/status |
|---|---|
| SQLite regression | 189 passed, 1 upstream deprecation warning, 156.13s; `standalone-sqlite-tests.xml` |
| PostgreSQL regression/concurrency/migrations | 189 passed, same warning, 390.64s on PostgreSQL 16; `standalone-postgresql-tests.xml` |
| Final asset/owner-isolation checks | 2 passed after favicon/source-label fixes |
| Lint/type/JavaScript syntax | Ruff passed; mypy passed for 42 engine files; node --check passed |
| Browser acceptance | Chrome/Playwright passed demo, desktop/mobile, authentication, subscription, custom draft/approval/subscription, logout; zero JavaScript errors; `browser-smoke.json` |
| Standalone Docker/TLS | Rebuilt image; all four assets present in installed wheel; HTTPS shell/assets/readiness pass, source-file access denied, private API 401; `standalone-container-smoke.json` |
| Backup/restore mechanics | Prior drill: all 36 tables matched by row count/content digest in separate synthetic databases |
| Dependency audit | Prior Windows/container Python inventories have no known vulnerabilities after pip patch. Docker Scout egress is now authorized, but scanner requires Docker login. OS audit and wheel-hash locking remain pending |
| Local TLS/ingress | Prior auth/admin/body cap/rate limit/log-redaction checks passed; no public deployment |
| Source collection | 50 real SEC filings downloaded, 10 per company, 0 errors; `sec-collection-summary.json`. Unlabeled and rights-review pending; no approved canonical event or live source-to-feed promotion |
| Genuine historical corpus/labels/holdout | Pending; 0 real historical events evaluated. Capture times cannot be backdated to filing dates |
| Independent product | Root UI and owned-narrative API implemented. Threadnote integration is no longer a release requirement |
| Git/remote CI | Local snapshot prepared using supplied email. GitHub plugin is enabled but repository tools are absent from this session; no remote configured or authenticated CLI account. No push/remote CI run claimed |
| Production operations | Domain/provider, production secrets/certificate, least-privilege DB roles, account lifecycle, quotas/retention and independent security review pending |
| Live delivery | Absent and intentionally disabled |

Commands: `.venv/Scripts/python -m pytest -q --junitxml=reports/standalone-sqlite-tests.xml`; same command with the dedicated disposable TEST_DATABASE_URL for PostgreSQL and output `standalone-postgresql-tests.xml`. The first PostgreSQL attempt hit database-startup errors; after pg_isready confirmed readiness the complete rerun passed. Test databases are separate from preview/demo databases.

Browser command: `.audit-venv/Scripts/python deploy/browser_smoke.py` with a fresh test identity and loopback preview. Packaged assets were separately checked from /tmp in the image so the source checkout could not mask missing wheel files. All 15 original manifest-protected files remain byte-identical.

Local preview uses http://127.0.0.1:8876, a synthetic database and an ignored token file. Docker test services are stopped after validation. Source-cache HTML, databases, credentials and logs are ignored by Git. Existing historical checkpoints retain the status from their respective sessions; this report and codex/STATUS.md supersede their Threadnote/contact/egress blockers.

Next recommended task: build a source-review workspace for the 50 staged SEC filings, with cited extraction and explicit duplicate/correction/rights review before ingestion into the private feed. Human labels and reviewed temporal facts remain required for P5 evaluation. See docs/standalone-product.md for the ordered backlog.
