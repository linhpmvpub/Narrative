# P4 checkpoint — 2026-11-20

## IMPLEMENTED

Continued the saved P3 checkpoint (128 tests) with the standalone P4 product layer. No mounted Threadnote application was replaced.

- Migration 0004 adds provisioned user/token identities, atomic idempotency receipts, private per-user cards, per-thread immutable snapshots, feedback history and revocable sharing. Frozen P1–P3 schema modules are unchanged.
- Bearer accounts resolve tenant/role on the server. Legacy API_TOKEN remains catalog-only. Exact ownership applies even within a tenant; global operator routes enforce RBAC. OpenAPI and structured errors cover new routes.
- Free tier enforces 3 stocks and 1 narrative under a user transaction lock. Scope compiler accepts at most 3 drivers and 2 hops, requires explicit company outcomes and disconfirmation, and appends immutable draft/approved versions. Templates remain separate from private drafts.
- Offline replay projects qualified cards with evidence, graph path, stance, missing conditions, next monitoring step and complete decision trace. Stock and narrative threads share one user/canonical-version card. Corrections append links to the prior version; history remains unchanged.
- Source-time chronology is separate from decision availability. Cursors retain a recorded cutoff. Custom approval time cannot be backdated into historical replay. Financial observations are discrete and source-gated; demo financial/price series are unavailable, not fabricated.
- Feedback is owner-only and history-preserving. WRONG creates a quality-review ticket; NOT_RELEVANT/USEFUL affect only personal relevance indicators. Neither changes global graph truth or source confidence.
- Private-by-default stories support explicit sharing with a revocable opaque link. Public allowlists remove identifiers, personal feedback, custom hypotheses/monitoring rules and decision traces.
- Operator replay gathers active threads for the existing dry-run planner. No live transport or background scheduling service is enabled.

Core additions: `engine/api/accounts.py`, `engine/api/product.py`, `engine/storybook/product.py`, `engine/models/schema_v4.py`, `engine/product_demo.py`, `alembic/versions/0004_product.py`, `tests/test_product.py`. Updated API registration/readiness/catalog isolation, transaction reuse in relationship review, configurable bounded policy hop scope, migration metadata, runbook and API contract.

## TESTED

Windows / Python 3.13 / temporary SQLite databases, external socket access prohibited by the test fixture. Local loopback permission was used for Starlette TestClient's asyncio self-pipe.

```
.\.venv\Scripts\python -m pytest -q -o faulthandler_timeout=20 --junitxml=reports/p4-tests.xml
146 passed, 0 failed, 0 skipped; 1 upstream Starlette/httpx deprecation warning; 136.40 seconds

.\.venv\Scripts\python -m ruff check engine alembic tests
All checks passed!

.\.venv\Scripts\python -m mypy engine
Success: no issues found in 34 source files
```

The 18 added P4 cases cover expired/revoked/legacy credentials, operator boundaries, cross-tenant and same-tenant ownership, concurrent quota enforcement, idempotent requests/conflicts, invalid scope, immutable approvals/edits, private catalog filtering, user/event bundling, source chronology and cursors, corrections, feedback review isolation, sharing redaction/revocation, custom replay availability/hop limits, operator replay retry and review evidence guards. Existing P1–P3 tests remain green. Every database-backed test exercises migration upgrade and downgrade on its disposable SQLite database.

Fresh `rie-p4-demo.db`: upgraded to 0004, seeded, explicitly initialized synthetic, ingested and replayed. `python -m engine.product_demo --as-of 2026-11-01T00:00:00Z --output reports/p4-F021-N08.json` succeeded twice. After retry: 10 templates, 40 candidate edges, 25 events / 26 versions, 310 policy traces, 8 user cards / 16 thread links, **0 alerts / 0 dispatch plans**. All P4 table DDL compiles for PostgreSQL; compilation is not runtime verification.

Artifacts: `reports/p4-tests.xml`, `reports/p4-validation.json`, `reports/p4-F021-N08.json`.

## QUALITY

F021/N08 is explicitly synthetic and private, path R026 → R027, actual stance INSUFFICIENT_EVIDENCE, conditional economic effect ADVERSE_IF_CONDITIONS_HOLD. Materiality remains unknown. No company outcome, point score or actual delivery is invented. The P3 synthetic baseline corpus/metrics are unchanged; no real-world precision or recall claim is made.

## PENDING / BLOCKERS

- Docker still reports missing `dockerDesktopLinuxEngine` pipe. PostgreSQL runtime testing remains blocked; CI is configured but no remote execution is claimed.
- Actual Threadnote repository/auth integration remains unavailable. The standalone provisioned-account implementation is not a claim of production integration or security certification.
- Live SEC identity verification, source rights approvals, real source-to-feed processing and calibrated materiality remain pending. Product projection currently consumes the explicit offline replay; no real push service or automatic scheduler is installed.
- P5 requires genuine approved historical events, human labels, chronological holdout evaluation, security/threat review and release decision. No synthetic substitute is presented as real evaluation. No launch recommendation is made.
- Git metadata/author configuration remain unavailable in this handoff folder, so no phase commit was created.

Operational details and limitations are recorded in `docs/integration_api.md` and `RUNBOOK.md`. Next phase is P5; retain all notification safeguards.
