# SEC review implementation — 2026-11-21

Implemented an independent operator workspace at `/review`, migration 0005 and separate real-source review store. Importer validates bounded local paths, SEC URLs, matching capture identity, hash and time before an atomic batch insert. It refuses synthetic databases, does not overwrite captures and is retry-safe. Plaintext is stored with a versioned transform/hash; no source HTML is executed.

Drafts preserve exact source spans and original capture time, validate issuer/metric/measurement basis, and require optimistic version checks. Corrections/reprints reference current independently approved earlier captures with matching canonical identity. Reviews require a different operator, version match and recorded rights/identity/citation/comparison confirmation. Writes use idempotency receipts; review history and prior draft versions are immutable through the API. Historical reads hide subsequent drafts/reviews. No endpoint publishes a canonical event, graph approval, feed card or notification.

50 real captures imported into `rie-sec-review.db`; repeat import inserted 0 and preserved all 50. Actual counts: 0 real drafts, 0 real reviews, 0 canonical events, 0 user cards. No real filing was authored or approved during browser testing. `reports/sec-review-import.json` records these counts.

| Check | Result |
|---|---|
| Complete SQLite regression | 206 passed, 1 upstream deprecation warning, 161.24s; `sec-review-sqlite-tests.xml` |
| Final SEC-focused SQLite tests | 19 passed, 1 warning, 35.62s; includes two tests added after full SQLite collection, covering registered metrics/write-key conflict and simultaneous operators; `sec-review-focused-tests.xml` |
| Complete PostgreSQL regression | 208 passed, 1 warning, 217.60s; migration upgrade/downgrade and all new review tests; `sec-review-postgresql-tests.xml` |
| Static checks | Ruff passed; mypy 45 engine files passed; JavaScript syntax passed |
| Chrome browser | Fabricated-source draft and independent approval passed; logout/source clearing and memory-only credentials passed. Real 50-filing workspace read-only passed. Desktop/mobile screenshots inspected; final bounded filing-list layout checked |
| Original specification integrity | All 15 protected file hashes unchanged |
| Container packaging | Rebuilt image; installed wheel has all 7 UI assets, final list-height CSS verified; review shell 200 and anonymous review API 401 from outside checkout; `sec-review-container.json` |

Commands: `.venv/Scripts/python -m pytest -q --tb=short --junitxml=reports/sec-review-sqlite-tests.xml`; equivalent full command with disposable TEST_DATABASE_URL for PostgreSQL. Focused suite: `pytest tests/test_sec_review.py -q`. Browser: `.audit-venv/Scripts/python deploy/sec_review_browser.py`. Browser tests use separate fabricated data under ignored source-cache; do not reuse a real account for automated approval tests.

Testing found and fixed two issues before handoff: SQLite timestamps needed explicit UTC serialization; asynchronous filing loads could reset an operator's in-progress form selection. The UI now makes the workspace inert during requests and clears stale forms on logout. Browser workflow passed after this fix.

Limitations: one draft chain/one claim per filing; form edits qualitative claims only, quantitative drafts can be read/reviewed. Source text loses HTML table structure, requiring review against the original. Staging review is not source/graph/materiality approval. No source-to-feed adapter or independently labeled historical benchmark is claimed. Production remains NO_GO; LLM and live delivery disabled.

Next: implement reviewed-source ingestion with receipt freshness, current source rights/identity and as-of gates, then integrate approved canonical events with the private feed. A real independent reviewer and approved calibration/labels are still needed. GitHub repository tools remain unavailable in this session; no push or remote CI run is claimed. Docker Scout now completed; zlib was patched and pip removed from runtime. Findings reduced 62 → 56, with 5 HIGH remaining and no fixed versions listed. See reports/image-audit-status.json; this is a production blocker, not a login blocker.

Start/access instructions: `docs/sec-review.md`. Current handoff: `codex/CHECKPOINT.md`.
