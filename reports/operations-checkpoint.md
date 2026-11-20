# Operational continuation — 2026-11-20

## Completed

- Started installed Docker Desktop and unblocked PostgreSQL. Used only a dedicated disposable container `rie-release-validation`, loopback port 55432, and separate `rie_test`, `rie_demo`, `rie_restore` databases.
- Ran both complete regression suites, including migration upgrade/downgrade, concurrent quota checks, ownership, corrections, privacy, temporal gates and evaluation. Generated the PostgreSQL synthetic F021/N08 sample with delivery disabled.
- Created a custom-format PostgreSQL dump and restored it into a different empty database. Read-only full-row digest/count comparison matched **all 36 tables**. The synthetic dump remains inside the disposable container; no credentials/row contents are exposed by the report.
- Audited captured Windows dependencies. The initial pip 25.2 finding contained 12 advisory entries, representing six distinct IDs with duplicates. Updated only the application venv's pip installer to 26.3. Final Windows and actual Linux application-container Python audits report no known vulnerabilities. No OS-image/unknown-vulnerability guarantee is made.
- Added digest-pinned application/proxy images, dependency version inventories, non-root/read-only API container, secret-file configuration, single-worker concurrency limits and exclusive operator replay guard.
- Tested loopback TLS with an explicit one-day local test certificate, nginx size/time/connection/rate limits, admin/docs blocking and log-redaction canaries. Health/readiness returned 200, unauthenticated private access 401, admin access 403, oversize requests 413. A 35-request burst produced 11 successes and 24 rate-limit responses. Bearer/path/query test canaries did not appear in local service logs.
- Prepared SEC collection tooling with ticker/submission CIK agreement, five distinct issuers, SNDK/WDC separation, bounded acquisition, true retrieval times, progressive manifests and pending-review classification. No bulk source download, approval, gold labeling or historical backdating occurred.
- Initialized local Git and verified secrets/virtual environments/databases are ignored. Pinned GitHub Actions to resolved tag commits and added dependency-audit jobs. No author/remote was supplied, so no commit, push or remote CI run was claimed.
- Exported OpenAPI and wrote deployment, SEC collection and Threadnote integration handoffs. Verified all **15 original handoff files** retain their manifest hashes.

## Verification

| Check | Result |
|---|---|
| SQLite full suite | **187 passed**, 0 failed/skipped, 139.51 seconds |
| PostgreSQL full suite | **187 passed**, 0 failed/skipped, 206.62 seconds |
| Ruff | All checks passed |
| Mypy | No issues in **41 source files** |
| PostgreSQL restore | 36 tables matched |
| Original manifest | 15 files, 0 changed |
| Windows/container Python dependency audits | No known vulnerabilities after pip update |
| nginx configuration and local TLS/ingress smoke | Passed |

Test command: `.venv/Scripts/python -m pytest -q -o faulthandler_timeout=30 --junitxml=<report>`; PostgreSQL additionally used the dedicated TEST_DATABASE_URL. Both suites have one upstream Starlette/httpx deprecation warning. Test fixtures prohibit external network sockets. Public package/image/advisory downloads and localhost validation were explicitly run with network permission; no live notification occurred.

Evidence: `release-sqlite-tests.xml`, `postgresql-tests.xml`, `postgresql-restore.json`, `postgresql-ingestion.json`, `postgresql-F021-N08.json`, `dependency-audit-before.json`, `dependency-audit.json`, `container-dependency-audit.json`, `container-packages.json`, `deployment-smoke.json`, `log-redaction.json`, `original-package-integrity.json`.

## Still blocked or data-dependent

Requested from the user: Threadnote repository path/URL; Git author name/email and remote; real SEC contact email. No reply was received while completing independent work. Production hosting/domain/secret-management decisions and an independent source/gold-label reviewer are also needed.

Real-source event extraction/deduplication, source rights/archive validation, graph review, materiality calibration, actual source-to-feed integration and independent historical evaluation remain pending. Staged filing metadata is not an approved economic event. No performance or investment claim is made.

The deployment is local, not published. Per-account/distributed quotas, retention, production DB roles, encryption/offsite backup operations, SSO, egress policy and independent penetration testing remain open. Dependency inventories are version-pinned but not wheel-hash locked; OS packages were not audited. The local test certificate expires and is not a production certificate. The replay lock is intentionally single-process and must be replaced before multi-worker scaling.

An additional Docker Scout image audit was attempted but **automatic approval review rejected the action before execution**: the scanner may send image-derived metadata/content from private project code to Docker's external service, and that specific egress was not authorized. An explicit user approval question was issued. No workaround or indirect image upload was attempted; OS/image vulnerability scanning remains blocked pending that decision. Completed Python dependency audits are unaffected.

Test services are stopped after validation; images/database state are retained for inspection. Docker Desktop remains running. No existing user database or directory was deleted.

## Suggested next task

**Private Threadnote fixture pilot plus real-source reviewer handoff.** Supply the missing repository/identity/contact details, integrate one private account with DELL/N08, and test corrections, feedback and sharing against a second account. Begin approved source collection at real capture times while a human reviewer prepares the gold corpus. Keep live notifications disabled and production NO_GO until the remaining gates have evidence.
