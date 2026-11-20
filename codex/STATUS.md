# Current project status — standalone continuation

Session handoff and exact resume instructions: **`codex/CHECKPOINT.md`** (2026-11-20).

The user's latest instruction supersedes the original Threadnote integration requirement: develop Narrative independently. Preserve the original manifest-protected specifications and fixture seeds. `TASKS.md` is the original checklist, not the current completion ledger.

- P0–P4 backend implementation and synthetic acceptance are complete; see phase reports.
- P5 evaluation/security/operations tooling is implemented; genuine labeled historical evaluation and production release gates remain open.
- Standalone Vietnamese UI added at `/`, with read-only synthetic F021/N08 demo and authenticated private workflows. New owner-scoped `GET /api/v0/narratives` supports custom narrative listing.
- Real SEC collection completed: 50 filings across exactly 5 companies, 0 acquisition errors. Files in ignored `source-cache/sec-review-2026-11-20`; every filing remains unlabeled and rights-review pending. No real event evaluated or source promoted to production.
- User authorized Docker Scout image-data transfer. The scan now requires Docker account login; it is no longer awaiting egress permission.
- GitHub plugin is installed/enabled, but this session exposes no GitHub repository tools; Git Credential Manager has no GitHub account and no remote is configured. Do not claim a push or remote CI run.
- Keep `SEND_NOTIFICATIONS=false`, `ALLOW_SYNTHETIC_LIVE=false`, `LLM_MODE=none`.

Current validation and blockers: `reports/release-v0.md`. Product start guide and ordered next steps: `docs/standalone-product.md`.

Next recommended implementation: source-review workspace for staged SEC filings, with cited extraction, duplicate/correction review and explicit approval before private feed ingestion. Independent rights, graph/materiality review and gold labels are not to be invented to close release gates.
