# Current project status — standalone continuation

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

Next recommended implementation: gated private-feed projection from reviewed canonical records, with current rights/review checks, verified graph and calibrated materiality. Independent reviews and gold labels must not be invented. Keep notifications disabled; canonical ingestion does not approve graph edges or enable delivery.
