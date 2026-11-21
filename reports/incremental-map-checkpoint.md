# Incremental source lifecycle and impact map — 2026-11-21

252 passed SQLite (297.44s), 252 passed PostgreSQL (398.33s); each suite has one existing Starlette/httpx deprecation warning and zero failures. Ruff, mypy53 files, JavaScript syntax and Chrome desktop/mobile checks pass.

Implemented:
- Migration0007: atomic per-company cursors and immutable collection receipts.
- Bounded recent/archive reconciliation, incremental backlogs, metadata corrections, conservative
  missing/uncovered classification and evidence-recorded operator withdrawal/restoration.
- Incremental per-owner projections and point-in-time invalidation of superseded/withdrawn cards.
- Interactive /map with company/as-of selectors, pan/zoom, evidence/conditions, hypothetical
  direction changes and the existing two-hop matcher. Demo and real data remain separated.
- Temporal eligibility badges and packaged seed topology verified by new regression tests.
- GitHub origin configured as https://github.com/linhpmvpub/Narrative; authenticated push dry-run
  succeeds. Source commit fe3b840 was pushed to main and GitHub CI run44908013042 passed all jobs, including both database suites and migration/replay. Existing CI includes JS checks and read-only repository permissions. The final handoff commit contains documentation/report changes only.

Real collection: 51 events/versions,31 owner cards/41 feed links,5 company cursors; no alerts or
confirmed real withdrawals. One new NVDA filing notice was added. Repeat collection created no
new versions/links. Source rights do not gate this private development flow. No source/graph
approval or economic claim was invented.

Browser evidence: reports/impact-map-{desktop,private,mobile}.png and impact-map-browser.json.
Tests include fifteen new cases beyond the previous237, plus the existing development-feed
regressions. Git history229 blobs and224 working files scanned against known runtime tokens;
none found. All15 manifest-protected files and their tracked Git blobs retain original hashes.

Live graph remains candidate-only; real metadata is not a financial observation. Heuristic
relevance/confidence are not calibrated probabilities or price predictions. Next quality work:
source-backed, period/unit-consistent financial observations, causal evidence and independent
holdout evaluation. Notifications stay disabled. Old image findings remain; no image rebuild or
new vulnerability scan in this milestone. See docs/incremental-impact-map.md and CHECKPOINT.
