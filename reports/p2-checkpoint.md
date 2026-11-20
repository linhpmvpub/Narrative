# P2 checkpoint — 2026-11-19

## IMPLEMENTED

- Offline `FixtureSourceAdapter` validates the entire JSONL input, enforces synthetic-only source contracts, limits input size and sorts by availability. No external requests or LLM calls.
- Migration 0002 adds database mode and immutable per-input/per-cutoff ingestion receipts. Existing v1 tables and seeds are preserved. The writer refuses production/unmarked databases; initialization refuses existing sources/events or reviewed relations.
- Transactional fixture ingestion stores document hashes, URL hashes, provenance, source clocks, synthetic headline evidence, canonical events and immutable versions. Reprints link to the original version. Declared corrections append a version linked through `supersedes_version_id`. Changed input-ID reuse fails and rolls back the batch. Concurrent retries serialize and create one version.
- As-of selection preserves the original before a correction became available. Future inputs are recorded as suppressed receipts but excluded from events until a later eligible import. Reprints of an older corrected version cannot revert current history.
- Independent structured-extraction models require source spans, comparison basis and decimal-safe values. Numerical comparisons reject incompatible concept, unit, quarter/year duration, fiscal calendar, accounting basis and actual/guidance class. Unknown fields and invalid JSON fail closed.
- SEC submissions/CompanyFacts acquisition has a declared User-Agent, two requests/second per shared client, bounded backoff/retries, response-size limits, hashes and immutable cache snapshots. Historical acquisition is cache-only and excludes snapshots retrieved after the cutoff. This follows the [SEC API endpoints](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and uses a rate below the [SEC fair-access maximum](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
- Company IR acquisition requires an exact HTTPS origin and dated reviewer/rights approval. Pending, blocked, missing or future approvals fail before fetching. Redirects are not followed. All adapter tests use mocked responses.
- Readiness now expects migration 0002. The runbook documents an isolated synthetic database and working ingestion commands; CI lint includes the new tests.

## TESTED

Actual final command:

```text
.\.venv\Scripts\python -m pytest -q -o faulthandler_timeout=20 --junitxml=reports/p2-tests.xml
82 passed, 1 warning in 28.94s
```

**82 passed / 0 failed / 0 skipped**, comprising the 45 existing tests and 37 new P2 tests. Environment: Windows, Python 3.13.7, isolated virtual environment, SQLite. Windows loopback access was granted for the API test client; tests block external network calls, and SEC/IR transports are mocked. The sole warning is the existing upstream Starlette/httpx test-client deprecation.

Also executed:

```text
python -m ruff check engine alembic tests
All checks passed!

python -m mypy engine
Success: no issues found in 19 source files

python -m pip check
No broken requirements found.

python -m alembic upgrade head
python -m engine.seed --config config
5 stocks, 42 entities, 10 narratives, 40 candidate relationships
```

The migration was applied to the existing local foundation database and a separate synthetic database. The suite also upgrades/downgrades disposable databases. All 15 original handoff files still match their supplied SHA256 manifest.

Actual fixture CLI:

```text
DATABASE_URL=sqlite:///rie-demo.db
python -m engine.ingest --demo --initialize-demo --fixture fixtures/events.jsonl --as-of 2026-11-01T00:00:00Z
```

| Outcome | Count |
|---|---:|
| New canonical fact | 25 |
| Duplicate/reprint | 1 |
| Suppressed | 2 |
| Review required | 1 |
| Rejected | 1 |
| Appended correction | 1 |
| Total fixture inputs | 31 |

After an identical CLI retry, the database still contains **25 events, 26 event versions, 31 receipts and 0 alerts**. No graph approvals were imported.

| Regression | Observed result |
|---|---|
| F029 reprints F001 | Same event version, no new canonical fact |
| F030 future publication | `future_available_at`; eligible only at a later cutoff |
| F031 corrects F017 | Version 2 links to version 1; October 20 view retains version 1 |
| F025 quality 0.30 | `low_evidence_quality`; no canonical event |
| F027 incompatible period | `incompatible_period`; review queue entry |
| F028 WDC/HDD confusion | `issuer_identity_mismatch`; rejected |

Machine-readable artifacts:

- `reports/p2-tests.xml`: actual JUnit test results.
- `reports/p2-fixture-ingestion.json`: initial CLI results for all 31 inputs.
- `reports/p2-fixture-retry.json`: identical retry, with idempotency markers.
- `reports/p2-correction-history.json`: actual F017 version snapshots before and after F031.

## PENDING / LIMITS

- This is a functioning **synthetic ingestion pipeline**, not live-market event production. Fixture canonical keys are explicitly supplied by the dataset. The normalized economic-key helper is ready for live integration, but verified issuer resolution and source-specific fact mapping must precede it.
- SEC/IR acquisition and independent extraction validation are implemented separately. A verified live document-to-event mapper, CIK snapshot workflow, metric/taxonomy mappings and real-source operating validation remain pending. No live SEC response was fetched to claim those checks passed.
- Fixture source spans refer to supplied synthetic headlines. The package has no real numerical values. F027/F028 explicitly encode negative scenarios; these are routed to rejection/review rather than pretending their null-valued payloads permit numeric validation. Actual numerical models have separate basis checks.
- F031 declares a correction and changes the source headline without revised values. Its version preserves unknown materiality and evidence quality. It is an auditable synthetic correction, not a verified material economic change. Illustrative stance labels are retained as metadata and cannot alone create a correction version.
- The as-of event helper is restricted to synthetic databases. Live historical replay needs actual availability snapshots and fully integrated source provenance. Neither this helper nor the ingestion receipts implement P3 scoring or dispatch decisions.
- P3 graph/stance/scoring, P4 story-entry correction links and user integration, and P5 real historical evaluation remain pending. Golden correction case G08's event/version portion is covered; its story-entry assertion belongs to P4. No baseline-performance or production-readiness claim is made.
- Acquisition throttling is per shared client. Multiple production workers need deployment-wide coordination. Rights approvals must explicitly cover any private source-text caching; nothing is published by these adapters.

## BLOCKERS

- PostgreSQL runtime validation: Docker's Linux engine is still unavailable (`dockerDesktopLinuxEngine` named pipe missing). SQLite tests and PostgreSQL DDL compilation pass; actual PostgreSQL execution remains unverified locally. CI contains PostgreSQL checks but was not run remotely.
- Live sources: no verified SEC identity mapping, configured contact User-Agent or reviewed IR rights registry was supplied. Mocked acquisition tests need none of these; live integration does.
- Production integration: the actual Threadnote repository/auth contracts remain unavailable. This folder is still not a Git repository and has no configured author, so no phase commit was created.

## Files added or changed

Added: `engine/adapters/{__init__,fixture,http_sources}.py`, `engine/ingestion/{__init__,contracts,service}.py`, `engine/ingest.py`, `engine/models/schema_v2.py`, `alembic/versions/0002_ingestion.py`, `tests/test_ingestion.py`, `tests/test_source_adapters.py`, and this report plus its JSON/XML evidence.

Updated: `alembic/env.py`, `engine/api/__init__.py`, `pyproject.toml`, `.github/workflows/ci.yml`, `RUNBOOK.md`, `docs/architecture_decisions.md`. Original seeds, fixtures, reference schema, task checklist and golden cases remain unchanged.
