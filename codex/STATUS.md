# Current project status — standalone continuation

## Financial observations + remote mobile preview — 2026-11-21 (latest)

- Schema head **0008** adds immutable SEC CompanyFacts snapshots. `engine/financials.py` extracts consolidated revenue, net income, operating income and gross profit; comparison operands have accession, filing URL/date, concept, USD unit, explicit periods, JSON pointers and capture SHA256. Same concept/unit and comparable year-over-year durations only. Nonpositive baseline has no percentage; conflicting values withheld; SNDK pre-spin periods excluded. These are reported actuals, not manually verified causal claims.
- Actual collection: **5 snapshots / 36 comparisons / 72 source operands checked**; all five issuers successful, retry all duplicate. Canonical counts unchanged:51 events/versions,31 cards/41 links,0 alerts. Raw captures and databases remain ignored. Source rights are not a blocker for this private development path, per user instruction.
- Feed and map show reported financial observations and provenance. Map uses distinct consolidated `reported_metric` nodes, never maps these into segment-specific causal nodes. Latest snapshot/as-of availability and canonical source identity/status control visibility; corrections retained, empty replacement/withdrawal withholds stale observations. Price impact/materiality UNKNOWN; stance insufficient evidence. Real graph still candidate.
- Remote access fixed: backend8888 remains loopback, read-only gateway8890 proxies only approved viewer/scenario routes, no admin endpoints or injected application credential. Cloudflare quick tunnel uses `--allowed-mail linhpm.vpub@gmail.com` and OTP. User explicitly approved Cloudflare processing private feed/email/request access token and **confirmed the map opens on phone remotely**. Do not ask for the same transfer approval again. Temporary URL is in ignored `secrets/mobile-preview.json`; do not commit the live URL. Tunnel stops if PC/process stops; hostname changes on restart. Existing member token remains necessary for private data; never print it.
- Browser desktop/mobile checks passed: financial detail/feed, four DELL metric nodes, read-only controls, no horizontal overflow/JS errors. Full SQLite **265 passed (354.34s)** and PostgreSQL **265 passed (494.78s)**; final focused **13 passed (23.18s)** after capability endpoint/UI update. One known Starlette/httpx warning per pytest run. Ruff, mypy56 files and JS syntax passed. Original15 manifest files unchanged; changed files scanned against runtime tokens. Reports: `financial-{collection,retry,provenance-check,browser}.json`, `financial-mobile-{state,sqlite-tests,postgresql-tests}.*`.
- Backend8888/gateway8890/tunnel left running; disposable test PostgreSQL stopped after validation. Old review/demo DBs need migration0008 before restarting with current code. Notifications remain false, LLM none. Instructions: `docs/financial-mobile.md`.
- GitHub: code commit **274f412975d322acd82b75a0ae6da52f1380049a** pushed to main; **CI passed** https://github.com/linhpmvpub/Narrative/actions/runs/44910850863 (dependency audit, lint/types/JS, SQLite/PostgreSQL, migration/seed/replay). This handoff only updates docs/report `[skip ci]`; details in `reports/financial-github-validation.json`. Older commit references below are historical.
- Next task: evidence-backed causal links between reported metric changes and segment/company drivers, then independently labeled holdout evaluation (including negative/ambiguous cases). Add amendment linkage across accessions before treating restatements as new economic events. No price prediction or live notification until evidence supports it.


Latest: incremental collector/lifecycle and interactive impact map implemented (schema0007).
51 real SEC metadata notices, 31 private cards / 41 links; zero alerts or fabricated withdrawals.
Final SQLite and PostgreSQL suites each pass252 tests; browser/lint/types/JS checks pass.
See docs/incremental-impact-map.md and codex/CHECKPOINT.md. Origin is now
https://github.com/linhpmvpub/Narrative; code commit fe3b840 is pushed and GitHub CI run44908013042 passed; earlier no-remote/login
statements below are historical. Next quality work: source-backed financial observations and
independent causal/impact evaluation, not further source-rights gating of this private prototype.

Latest 2026-11-21: opt-in private development feed implemented under the user's explicit
source-rights/verified-graph/materiality bypass for development. 50 real SEC metadata notices,
30 owner cards / 40 thread links in separate rie-dev-feed.db; no alerts, no approvals. Public
sharing excludes development events. Preview port8888; docs/development-feed.md and CHECKPOINT
contain current commands. Final SQLite and PostgreSQL suites each pass237 tests; lint/types/JS/browser checks pass. The strict reviewed impact-feed path remains future work.

Session handoff and exact resume instructions: **`codex/CHECKPOINT.md`** (updated 2026-11-21).

The user's latest instruction supersedes the original Threadnote integration requirement: develop Narrative independently. Preserve the original manifest-protected specifications and fixture seeds. `TASKS.md` is the original checklist, not the current completion ledger.

- P0–P4 backend implementation and synthetic acceptance are complete; see phase reports.
- P5 evaluation/security/operations tooling is implemented; genuine labeled historical evaluation and production release gates remain open.
- Standalone Vietnamese UI added at `/`, with read-only synthetic F021/N08 demo and authenticated private workflows. New owner-scoped `GET /api/v0/narratives` supports custom narrative listing.
- Real SEC collection completed: 50 filings across exactly 5 companies, 0 acquisition errors. Files in ignored `source-cache/sec-review-2026-11-20`; every filing remains unlabeled and rights-review pending. No real event evaluated or source promoted to production.
- Docker Scout scan completed on 2026-11-21 under existing egress authorization. After zlib patch and runtime pip removal: 56 findings in 13 packages (5 HIGH); no fixed versions listed for the remaining findings. Login is no longer blocked; production remains NO_GO. See reports/image-audit-status.json.
- GitHub plugin is installed/enabled, but this session exposes no GitHub repository tools; Git Credential Manager has no GitHub account and no remote is configured. Do not claim a push or remote CI run.
- Keep `SEND_NOTIFICATIONS=false`, `ALLOW_SYNTHETIC_LIVE=false`, `LLM_MODE=none`.

Current validation and blockers: `reports/release-v0.md`. Product start guide and ordered next steps: `docs/standalone-product.md`.

SEC review workspace implemented on 2026-11-21: migration 0005, bounded offline import, versioned drafts, citation/issuer/capture checks, independent operator review, retry/concurrency guards and historical reads. All 50 captures imported into a separate real-source review DB; no real draft/review/feed publication was created. See `docs/sec-review.md` and `reports/sec-review-checkpoint.md`.

Reviewed-source ingestion adapter implemented in schema 0006: explicit versioned capture permissions, independent review and fresh rights/version/as-of checks, atomic canonical event/evidence creation, retry/dedup, cross-capture corrections and historical operator snapshots. Permissions/ingestion are API-only in this milestone. Review DB backed up and migrated; all 50 real captures remain unapproved with zero canonical events. See `docs/reviewed-ingestion.md` and `reports/reviewed-ingestion-checkpoint.md`.

Deferred verified-impact work: gated private-feed projection from reviewed canonical records, with current rights/review checks, verified graph and calibrated materiality. The current next development task is incremental collection and correction/withdrawal handling for the private informational feed. Independent reviews and gold labels must not be invented. Keep notifications disabled; canonical ingestion does not approve graph edges or enable delivery.
