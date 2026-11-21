# Release v0 — private development feed (2026-11-21)

Final full suites: **237 passed SQLite (239.74s), 237 passed PostgreSQL (290.99s)**. Each has one existing upstream Starlette/httpx deprecation warning; zero failures. Nine new development-feed cases include concurrent ingestion/projection, identity/hash/time rejection, private ownership, sharing exclusion, temporal pagination, opt-in isolation and A → B → A correction history.

User-authorized development bypass implemented as an explicit opt-in private informational feed.
50 real SEC metadata canonical notices; 30 owner cards / 40 thread links; 0 alerts, 0 approvals.
Public shares exclude all development notices. Live delivery stays disabled. Ruff/mypy49 files,
JS syntax, Chrome desktop/mobile and original manifest integrity pass. No new migration (0006).
See `reports/development-feed-checkpoint.md` and `docs/development-feed.md`.

No blocker remains for this development milestone. Production remains NO_GO: independent
source/impact evaluation, benchmark labels, account/operational readiness and prior image
security findings remain open. No image rebuild/new Scout scan or remote push/CI in this task.
Next: incremental collection and correction/withdrawal handling for the private feed.

The sections below are historical milestones; their earlier test counts and next tasks are superseded.

# Release v0 — reviewed canonical ingestion (2026-11-21)

Latest milestone: schema 0006 connects independently reviewed SEC extractions to canonical events behind explicit versioned rights/identity permissions and current/as-of gates. Final full suites: **228 passed on SQLite and 228 passed on PostgreSQL**, one upstream deprecation warning each. Ruff/mypy (48 files), packaged-container end-to-end ingestion and local read-only readiness checks passed. See `reports/reviewed-ingestion-checkpoint.md` and `docs/reviewed-ingestion.md`.

50 real captures remain unchanged, with zero real approvals/canonical events. Canonical ingestion does not publish a private feed, approve graph/materiality or send notifications. Production remains NO_GO due to independent review/evaluation/operational gates and prior unresolved image findings. Next implementation: gated private-feed projection. No remote push/CI is claimed.

The remaining sections retain earlier milestone evidence; their older schema/test counts are historical.

Current milestone: operator SEC review workspace is implemented with migration 0005 and separate real-source staging. 50 captures imported; 0 real drafts/reviews/events/feed cards. Complete PostgreSQL suite: **208 passed**. SQLite full suite: **206 passed**, followed by **19 focused tests passed** including two new cases (208 distinct tests covered). Chrome workflow and responsive checks passed; Ruff/mypy (45 files)/JavaScript syntax passed. See `reports/sec-review-checkpoint.md` and `docs/sec-review.md` for current evidence and operation.

Docker Scout now completed: patched zlib and removed runtime pip, reducing findings from 62 to 56 (5 HIGH). The remaining entries have no fixed version listed by Scout. Production remains NO_GO; login is no longer blocked. See `reports/image-audit-status.json`.

The table below retains the previous standalone milestone evidence; its older counts are historical. Review approval remains staging-only. The next implementation is a gated reviewed-source ingestion adapter, not construction of the now-completed review screen.

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
