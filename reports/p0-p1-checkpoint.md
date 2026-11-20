# P0/P1 checkpoint — 2026-11-19

## IMPLEMENTED

- Standalone Python backend in the nested specification folder. Architecture audit and integration boundary documented. Original Threadnote application was not available; no UI was modified.
- All 22 reference tables represented in Alembic revision 0001, SQLAlchemy metadata and core ORM mappings. PostgreSQL-native UUID/JSONB/timestamptz and SQLite test compatibility.
- Pydantic Entity, Stock, Relationship, Narrative, NarrativeVersion and NarrativeDriver contracts. Transactional, idempotent seed import of 5 stocks, 42 entities, 10 templates and 40 candidate edges. Unknown nodes, duplicates, invalid intervals, scope and monitoring conditions rejected.
- SNDK/WDC separation, pending identity handling and trading effective date. SEC ticker/CIK verification remains pending by design; no invented identifiers.
- Evidence-backed candidate approval with atomic evidence links and before/after review audit. Synthetic, unavailable, unlicensed, uncited and unreviewed evidence rejected. Candidate-only edges cannot pass live eligibility. Actual recording time prevents retroactive approval leakage.
- Fail-closed runtime flags; no LLM or notification provider. FastAPI health/readiness and authenticated catalog endpoints. Docker Compose and PostgreSQL CI template. Isolated local virtual environment and installed dependency snapshot.

## TESTED

Final environment: Windows, Python 3.13.7, isolated `.venv` with system packages disabled, SQLite. Tests run without external network requests; Windows loopback permission was required for the API test client's asyncio event loop.

Actual final command and output:

```text
.\.venv\Scripts\python -m pytest -q -o faulthandler_timeout=20
45 passed, 1 warning in 12.74s
```

**45 passed / 0 failed / 0 skipped.** One upstream Starlette warning deprecates its httpx test-client integration; it does not fail tests. The supplied package integrity test is included in the count. This is the P0/P1 suite, not a claim that all 22 golden scenarios have been implemented.

Other executed checks:

```text
python -m alembic upgrade head
python -m engine.seed --config config
  stocks=5, entities=42, narratives=10, candidate_relationships=40
  identity_status=pending_SEC_verification
python -m mypy engine
  Success: no issues found in 11 source files
python -m ruff check engine alembic tests/test_foundations.py tests/conftest.py
  All checks passed!
python -m pip check
  No broken requirements found.
Original handoff SHA256 verification
  15 files unchanged
```

Tests create/migrate/seed disposable databases and downgrade them during teardown. Coverage includes idempotency, cardinalities, ORM lookup, every candidate edge, SNDK dates and issuer rejection, malformed seeds, immutable narrative import, atomic failed review, successful audited review, backdated review, narrative availability, FK/check constraints, authenticated/unauthenticated API calls, readiness and settings. PostgreSQL DDL compilation passed; PostgreSQL execution has not been verified locally.

## PENDING

- P2: event/fixture ingestion, canonical deduplication/corrections, source adapters and explicit unit/period validation.
- P3: full temporal revision selection, two-hop matching, stance/scoring and decision traces. The F021/N08 card is still only a supplied expected fixture; no generated engine response is claimed.
- P4: real user/tenant authentication, subscriptions, feedback, storybook and dry-run dispatcher. Current single-token catalogs are development-only.
- P5: executable remaining golden cases, all security tests, three-baseline comparison and 50–100 source-backed human-labeled historical events. Historical evaluation and all performance metrics are **pending**.
- Python 3.12 and PostgreSQL 16 runtime checks are configured in CI but not executed in this environment. No production readiness claim.

## BLOCKERS

- Docker Desktop's Linux engine remains unavailable: `docker info` reports missing `dockerDesktopLinuxEngine` pipe, including outside the sandbox. Starting Docker Desktop did not make the engine available. PostgreSQL migration/runtime verification needs a functioning local Docker/WSL2 engine or another test database.
- No existing Threadnote repository or integration/auth contracts were mounted.
- No Git repository or configured Git author name/email was present. Phase commits were not created; no author identity was invented. The files are ready for review and import into the intended repository.

## Added files

```text
.env.example
.gitignore
.github/workflows/ci.yml
pyproject.toml
requirements.lock.txt
docker-compose.yml
alembic.ini
alembic/env.py
alembic/versions/0001_foundations.py
engine/__init__.py
engine/settings.py
engine/db.py
engine/seed.py
engine/identity.py
engine/models/__init__.py
engine/models/contracts.py
engine/models/schema_v1.py
engine/graph/__init__.py
engine/graph/review.py
engine/api/__init__.py
tests/conftest.py
tests/test_foundations.py
docs/architecture_decisions.md
docs/integration_api.md
RUNBOOK.md
reports/p0-p1-checkpoint.md
```

Local generated `.venv/`, caches and `rie-local.db` are ignored. The database contains candidate seeds only. The original specification, config, fixtures, golden cases and task checklist were preserved byte-for-byte.
