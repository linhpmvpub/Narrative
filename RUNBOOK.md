# P0–P5 local runbook

Run commands from the nested `relationship_impact_engine_v0` folder containing `pyproject.toml`. Implemented: schema/seeds, source adapters, synthetic ingestion/replay, temporal graph policy, private product APIs, evaluation tooling and local security/deployment controls. Real-source approvals, independent historical labels/evaluation and actual Threadnote integration remain pending. Live notifications stay disabled.

Latest operational evidence: `reports/operations-checkpoint.md`. PostgreSQL is now validated alongside SQLite (187 tests each), the synthetic restore drill matched all 36 tables, and loopback TLS/ingress tests passed. Test services were stopped with their state retained. See `docs/deployment-validation.md` for restart/secret/database requirements, `docs/real-source-collection.md` for SEC staging, and `docs/threadnote-handoff.md` for host integration. Local Git is initialized; author and remote still need user configuration.

## Windows

Install Python 3.12 and Docker Desktop with the WSL2 backend. Start Docker Desktop and wait until `docker info` succeeds. Then:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d db
$env:DATABASE_URL = 'postgresql+psycopg://rie:local_dev_only@localhost:5432/rie'
$env:LLM_MODE = 'none'
$env:SEND_NOTIFICATIONS = 'false'
$env:ALLOW_SYNTHETIC_LIVE = 'false'
$env:API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
python -m alembic upgrade head
python -m engine.seed --config config
python -m pytest -q
python -m mypy engine
python -m ruff check engine alembic tests
python -m uvicorn engine.api:app --host 127.0.0.1 --port 8000
```

Python commands read environment variables, not `.env` automatically. Docker Compose reads `.env`; keep its database password synchronized with DATABASE_URL. The displayed password is local development only. `.env` is ignored by Git. Use the token only locally; do not commit it.

`requirements.lock.txt` records the exact packages used for the final local verification. To reproduce that environment, install it with `python -m pip install -r requirements.lock.txt`, followed by `python -m pip install -e . --no-deps`. It is a version snapshot, not a wheel/hash lock; Python 3.12/Linux installation is checked by CI separately.

## WSL2/Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
docker compose up -d db
export DATABASE_URL='postgresql+psycopg://rie:local_dev_only@localhost:5432/rie'
export LLM_MODE=none SEND_NOTIFICATIONS=false ALLOW_SYNTHETIC_LIVE=false
export API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
alembic upgrade head
python -m engine.seed --config config
pytest -q
uvicorn engine.api:app --host 127.0.0.1 --port 8000
```

## Offline local fallback

Once dependencies are installed, tests, seed loading and fixture ingestion make no external requests. When PostgreSQL is unavailable, explicitly set `DATABASE_URL=sqlite:///rie-local.db`, then run migrations and seed commands above. Seed loading does not import a demo-approved graph or fixture events. SQLite checks cannot certify PostgreSQL behavior.

## P2 synthetic ingestion

Use a **separate database**. Migration 0002 adds database mode and ingestion receipts without altering the frozen v1 schema. The initializer refuses a production marker, existing source/event data or reviewed relationships. After marking a database synthetic, it must remain synthetic. The service refuses fixture ingestion into an unmarked or production database.

```powershell
$env:DATABASE_URL = 'sqlite:///rie-demo.db'
python -m alembic upgrade head
python -m engine.seed --config config
python -m engine.ingest --demo --initialize-demo --fixture fixtures/events.jsonl --as-of 2026-11-01T00:00:00Z
# Safe retry: immutable receipts and version IDs prevent duplicate writes.
python -m engine.ingest --demo --fixture fixtures/events.jsonl --as-of 2026-11-01T00:00:00Z
```

For WSL2, replace the environment assignment with `export DATABASE_URL=sqlite:///rie-demo.db`; the Python commands are identical. Restore the non-demo DATABASE_URL before using other services. No graph approvals or notifications are produced.

The supplied 31 records produce 25 new canonical events, one reprint, one appended correction, two suppressed inputs, one review-required input and one rejected input. The database holds 25 events and 26 versions. F030 can be imported using a later cutoff without appearing in an earlier snapshot. `engine.ingestion.service.versions_as_of` returns the latest visible version in a synthetic database. It is not the P3 scoring/replay CLI.

Fixture source spans point into the supplied synthetic headline. No real article, numeric values or source approval is invented. F027 and F028 carry explicit negative-scenario event types; those flags map to period/identity validation outcomes, since their null-valued claims cannot support numerical comparison. Real numeric extraction uses independent unit, duration, fiscal-calendar, concept, accounting-basis and actual/guidance checks.

F031 supplies a correction declaration and changed source headline but no revised numeric values. Its correction is recorded with `materiality: UNKNOWN` and unknown evidence quality, not interpreted as a verified economic change. Illustrative stance labels are retained only as fixture metadata; changing a label alone cannot create a correction version.

## Source adapter limits

`SECSourceAdapter` provides submissions and CompanyFacts acquisition using an injected `SourceClient`. Supply a descriptive User-Agent with your actual contact email. The client serializes calls to two requests/second, retries transient failures at most four attempts, rejects redirects, limits decoded bodies to 5MB and supports content/URL-hashed disk snapshots. Share one client per acquisition worker; deployment-wide rate coordination across multiple workers is not implemented.

Historical acquisition is cache-only: a snapshot retrieved after the cutoff is unavailable even if its contents describe older periods. This prevents a fresh aggregate CompanyFacts response from leaking corrections into a historical evaluation. Live field-to-metric mapping and SEC ticker/CIK verification remain pending.

`IRSourceAdapter` requires an exact HTTPS origin and a dated rights approval with reviewer and note. Pending/blocked origins and redirected requests are rejected. No company IR origin is approved by default. Configure private caching only when the approval covers storage; do not republish source text. Adapters return source documents, not inferred events or alert decisions. Tests inject mocked HTTP responses; no real SEC or IR acquisition was performed for validation.

The test suite uses fresh temporary SQLite databases by default. Set `TEST_DATABASE_URL` only to a **dedicated disposable PostgreSQL test database** to run backend checks. Each test migrates and then downgrades that database; never point this variable at user data. CI provides its own disposable database.

## P3 graph and policy replay

Migration 0003 adds immutable demo contexts, policy traces (including suppressed inputs), and dry-run dispatch plans. It leaves the original candidate graph and real narrative version timestamps intact. A complete demonstration from a separate database is:

```powershell
$env:DATABASE_URL = 'sqlite:///rie-p3-demo.db'
python -m alembic upgrade head
python -m engine.seed --config config
python -m engine.ingest --demo --initialize-demo --as-of 2026-11-01T00:00:00Z
python -m engine.replay --dry-run --as-of 2026-11-01T00:00:00Z --output reports/p3-replay.json --sample-output reports/p3-F021-N08.json --baseline-output reports/p3-baselines.json
```

On WSL2 use `export DATABASE_URL=sqlite:///rie-p3-demo.db`; the Python commands are identical. The replay can be retried: it checks existing trace contents and never overwrites a decision. Changed context inputs produce a new content-addressed context. A policy behavior change must receive a new algorithm revision/version before replay; changing an existing trace fails closed.

All 31 inputs are evaluated against all 10 templates. F030 remains excluded from the historical corpus but receives a future-source suppression trace for every template. The baseline comparison uses the same 30 eligible inputs/300 pairs for B0 and V0. B1 is explicitly unavailable with LLM mode disabled. Descriptive match counts are not precision or recall claims.

`fixtures/p3_demo_policy.json` supplies explicitly synthetic, source-headline-bound directional observations, required conditions and company-metric targets. It never supplies final stance labels or numeric materiality. The original fixture's `illustrative_stance`, `direction_for_demo`, `narrative_target` and `m_test_input` are not used to decide stance or materiality. Quality values remain labeled synthetic test inputs. Sector events do not become zero-hop issuer disclosures merely because the fixture has a primary ticker.

F021/N08 uses R026 → R027. Its stance is INSUFFICIENT_EVIDENCE, with conditional SUPPORTS and ADVERSE_IF_CONDITIONS_HOLD shown separately. Contracted cost increases and inadequate price/rebate/mix offsets must be confirmed. Materiality is unknown, so the score is null; bounds show the effect of the missing M component without inventing it. No live notification can be sent.

`engine.dispatch.dry_run.plan_dry_run` bundles one canonical version per user across threads, respects quiet hours/minimum interval/daily cap, defaults to a kill switch, and never calls a provider. P4 replay gathers active subscriptions into one user batch. No background scheduler or live provider is installed.

## P4 private product demonstration

Use a separate synthetic database. These commands do not enable live delivery:

```powershell
$env:DATABASE_URL = 'sqlite:///rie-p4-demo.db'
python -m alembic upgrade head
python -m engine.seed --config config
python -m engine.ingest --demo --initialize-demo --as-of 2026-11-01T00:00:00Z
python -m engine.product_demo --as-of 2026-11-01T00:00:00Z --output reports/p4-F021-N08.json
python -m engine.api.accounts --tenant local-demo
python -m uvicorn engine.api:app --host 127.0.0.1 --port 8000
```

The generated artifact is a private synthetic N08 card with a shared DELL stock-thread link. The demo command creates an isolated demo account; use the separate provisioning command to obtain your own 30-day token. To exercise admin routes locally, provision a separate account with `--admin`; this is a global operator role. Do not reuse operator tokens in a frontend. Account tokens require migration 0004. Set `rie_tokens.revoked=true` to revoke a token. The legacy `API_TOKEN` remains catalog-only.

See `docs/integration_api.md` for request contracts, idempotency, custom version approval, sharing and temporal behavior. New subscriptions are projected on the next explicit operator replay. `POST /api/v0/admin/fixtures/replay` takes `{"demo":true,"as_of":"2026-11-01T00:00:00Z"}` and refuses a production database. Retrying resumes projections without rewriting history. Each other mutation needs an `Idempotency-Key` header; retry with the same key and exact body, use a fresh key for a new action. Live settings stay false.

Run `python -m pytest -q -o faulthandler_timeout=20 --junitxml=reports/p4-tests.xml`, `python -m ruff check engine alembic tests`, and `python -m mypy engine`. On sandboxed Windows, TestClient may require permission to use local loopback for its asyncio self-pipe; no external network is used. PostgreSQL runtime validation still requires a running Docker Linux engine or a dedicated disposable test instance.

## Failure recovery and operational limits

### P5 security review

Read `docs/threat_model.md` and `reports/release-v0.md` before deployment. The API now enforces a 64 KiB request-body limit and no-store/no-referrer/nosniff response headers. Valid requests require unchanged auth/ownership/idempotency controls. Malformed Content-Length returns 400; oversize bodies return 413. Financial story observations must pass the same citation proof checks used for relationship review.

Keep the service on loopback/private infrastructure. Internet exposure still requires TLS, rate/connection/deadline limits, bounded operator replay, token-safe logs, protected backups and dependency review. Public-share URL tokens must be redacted from proxy access logs; idempotency receipts also contain raw share URLs. Account-token revocation does not revoke active story shares, which must be disabled separately. Do not claim database encryption, PostgreSQL validation or restore drills have occurred.

Run `python -m pytest -q -o faulthandler_timeout=20 --junitxml=reports/p5-security-tests.xml` for the security checkpoint regression suite. No endpoint or environment flag can enable live notification transport in this release.

### P5 offline evaluation tooling

The empty collection workspace is `evaluation/historical-v0/`; contracts and commands are documented in `docs/historical_evaluation.md`. Use `python -m engine.evaluation.cli` with `init`, `freeze`, `label-template` or `evaluate`. No command acquires data or changes notification settings. Freeze refuses empty datasets; label templates require human completion; outputs refuse overwrite. Keep the original manifest and holdout untouched when experimenting with policy changes.

Reports `reports/eval-v0.md`, `reports/quality-errors.md` and `reports/cost-v0.md` explicitly mark historical performance and unmeasured costs pending. Do not substitute fixture results for a real corpus. Run `python -m pytest -q --junitxml=reports/p5-tooling-tests.xml` for the complete regression suite.

- `readyz` returns 503 for missing migrations or database outage. Restore connectivity, run `alembic current`, then `alembic upgrade head` before retrying.
- Candidate seed imports are atomic and may be retried. Validation or conflicting immutable narrative versions fail instead of overwriting. Update narrative version numbers intentionally when changing hypotheses.
- Review failures roll back status, evidence links and revision insertion together. Never repair an approval by setting status directly in SQL. Reviews need approved non-synthetic source documents, offsets, reviewer and timestamps.
- Stop the API with Ctrl+C. `docker compose stop` retains the database volume. Do not remove volumes as routine recovery. Back up PostgreSQL before any destructive migration; downgrade is intended for disposable tests here.
- `SEND_NOTIFICATIONS=true`, `ALLOW_SYNTHETIC_LIVE=true` or a non-none LLM mode are unsupported and rejected. No provider delivery is implemented.
- `SNDK` seed alias starts at trading on 2025-02-24; company separation is 2025-02-21. Live alias lookup remains unknown until SEC verification. WDC does not resolve to SNDK.
- Seed templates have import-time availability. October fixture replay uses separate explicitly synthetic snapshots; it never backdates production templates.
- Live graph matching reads audited revision snapshots with evidence IDs, rather than trusting current mutable status. Legacy approvals without evidence IDs in their audit snapshot fail closed and require a reviewed migration before live routing.
- Remaining live-source integration, P5 security/release review, PostgreSQL runtime verification, Threadnote identity integration and human-labeled historical evaluation must pass before release. P4 account/ownership checks are tested locally; this is not a production security certification. All supplied market events remain synthetic.
