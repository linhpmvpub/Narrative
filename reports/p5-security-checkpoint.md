# P5 security checkpoint

## IMPLEMENTED

Continued from the P5 evaluation-tooling checkpoint with a scoped source-level threat review. Reviewed API identity/ownership/operator boundaries, source/fixture acquisition, temporal proofs, immutable writes, feedback, sharing, dry-run dispatch, evaluation integrity and deployment configuration. No external source was contacted and no notification provider was enabled.

Verified and fixed four application gaps:

- Requests previously reached JSON parsing without an application body cap. New pure-ASGI middleware enforces 65,536 bytes, checks declared and actual streamed lengths, rejects malformed/duplicate/mismatched Content-Length with 400 and oversize bodies with 413.
- Private/share responses lacked cache/referrer controls. Middleware now adds no-store, no-referrer and nosniff headers to responses passing through it, including expected error paths.
- Non-ASCII catalog bearer credentials could raise a string-comparison TypeError. Encoded comparison now returns normal authentication failure, with a credential-length bound.
- Financial observations checked source rights and clocks but did not reuse the full reviewed-citation proof gate. They now require a matching HTTPS document citation, source claim offsets, a nonblank reviewer and valid clocks; source creation must precede the cutoff. Whitespace-only reviewer IDs fail the shared proof check.

Added `engine/api/security.py` and `tests/test_security.py`; updated API registration/auth comparison, financial observation reading and shared evidence review. No schema migration or existing snapshot rewrite was needed. Existing synthetic sample artifacts remain unchanged.

Published `docs/threat_model.md` and `reports/release-v0.md`, updated `RUNBOOK.md` and `docs/integration_api.md`. The threat model records controls and residual limits across prompt injection, licenses, SSRF/egress, auth/tenant privacy, provenance, sharing, audit storage, retries/recovery, resource exhaustion and evaluation integrity.

## TESTED

- Initial focused security run: 15 passed; subsequently added the whitespace-reviewer regression for a total of 16 new security cases in the full suite.
- Ruff: all checks passed. Mypy: no issues in 37 source files.
- Final full suite: **183 passed, 0 failed, 0 skipped**, one upstream Starlette/httpx deprecation warning, **124.80 seconds** on Windows/Python 3.13 with disposable SQLite databases. Command: `.\.venv\Scripts\python -m pytest -q -o faulthandler_timeout=20 --junitxml=reports/p5-security-tests.xml`. Local loopback permission was used for TestClient/asyncio; tests prohibit external socket connections. Evidence: `reports/p5-security-tests.xml`.
- Rechecked `docker info --format '{{.ServerVersion}}'`: failed because `dockerDesktopLinuxEngine` pipe is missing. No PostgreSQL runtime or remote CI success is claimed.

## PENDING / BLOCKERS

This is a local source review with regression tests, not an external penetration test or deployment security certification. Internet deployment still requires TLS, ingress time/rate/concurrency limits, replay/storage quotas, safe logging, restricted DB/backups, token/SSO integration, dependency review and a restore drill. Raw public-share URLs exist in idempotency receipts; protect these records and redact bearer-link paths from logs. Revoking an account token does not itself revoke active public shares.

Source caches and manually supplied evaluation trace hashes remain trusted local/operator inputs, not independently authenticated archives. DNS/private-address egress enforcement and a complete temporal source-rights ledger are pending. Actual Threadnote integration and real source-to-feed processing remain unavailable. No real historical corpus has been evaluated. PostgreSQL validation remains blocked by Docker. No Git phase commit was made in the non-Git handoff workspace.

**Release decision: NO_GO.** Scoped review and fixes are complete; production release gates are not. Live notifications remain disabled. See `reports/release-v0.md` for the outstanding gate list.
