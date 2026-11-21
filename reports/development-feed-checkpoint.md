# Private development feed — 2026-11-21

Final full suites: **237 passed SQLite (239.74s), 237 passed PostgreSQL (290.99s)**. Each has one existing upstream Starlette/httpx deprecation warning; zero failures. Nine new development-feed cases include concurrent ingestion/projection, identity/hash/time rejection, private ownership, sharing exclusion, temporal pagination, opt-in isolation and A → B → A correction history.

Implemented the user-authorized development bypass for source rights, verified graph and
materiality. This is explicit opt-in informational metadata, not verified impact analysis.
All live notification flags remain false and no dispatch path is invoked.

- SEC submissions metadata for 5 companies: 50 canonical notices, 50 event versions.
- Private preview: 30 owner cards, 40 links across DELL/NVDA/MU/N08 threads.
- Source remains pending; zero real source permissions, reviews, alerts or metric observations.
- Retry: all 50 duplicates, zero new links. Versioned metadata corrections include A → B → A;
  stale captures cannot revert newer state. PostgreSQL mode lock serializes ingestion and
  per-owner locks serialize projection against subscriptions and concurrent refreshes.
- Private owner and temporal controls hold; public sharing filters development notices before
  pagination. Default flag false hides them; existing strict reviewed ingestion remains intact.
- Capture and knowledge clocks remain separate from date-only filing metadata. No backdating.
- Chrome desktop/mobile login and four feeds pass; no horizontal overflow or JavaScript errors.
- Ruff, mypy49 files, JS syntax pass. All 15 original manifest-protected files unchanged.
- No schema change: head0006. Updated OpenAPI, settings example, run guide and checkpoint.

Evidence: development-feed-collection.json, development-feed-retry.json,
development-feed-state.json, development-feed-preview.json, desktop/mobile screenshots,
and development-feed-{sqlite,postgresql}-tests.xml.

Local preview: http://127.0.0.1:8888, separate ignored rie-dev-feed.db.
The original SEC review database and synthetic demo were preserved. Secrets and raw caches
remain Git-ignored. No remote push, image rebuild or new Scout scan in this milestone.

Limitations: metadata-only filing notices; no full-text news extraction, withdrawal detection,
cross-accession amendment grouping or automatic collection schedule. The small pilot projects
stored versions in memory; incremental projection is next. Production remains NO_GO under
previous security/evaluation gates (last image scan: 56 findings, 5 HIGH; not rescanned here).
