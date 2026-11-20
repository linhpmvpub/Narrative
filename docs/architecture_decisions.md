# P0/P1 architecture decisions

Audit date: 2026-11-19 (Asia/Bangkok).

The mounted handoff contains a nested specification package, not an existing Threadnote application. No frontend, authentication implementation, database service, Git history, or AGENTS.md was found in the project tree. The parent directory contains duplicate handoff documents. Implementation lives beside the canonical `config/`, `fixtures/`, and `schemas/` folders in `relationship_impact_engine_v0/`; the original specification and fixtures remain unchanged. Production integration is pending access to the actual Threadnote repository.

The START HERE document asks for all phases eventually but explicitly says to implement P0 and P1 only in the immediate first command. This checkpoint follows that narrower scope. P2–P5 are not represented as complete. No frontend or user data was modified.

## Accepted architecture

- Python 3.12 deployment target; FastAPI/Pydantic 2; SQLAlchemy 2; Alembic; PostgreSQL 16. Local verification currently uses installed Python 3.13.7.
- The 22 supplied reference tables are translated into a frozen `engine/models/schema_v1.py`. Migration 0001 imports this frozen definition; future schema changes must use new migration revisions, never edit the frozen version. JSON uses JSONB on PostgreSQL. UUIDs are generated in application defaults, removing the pgcrypto installation requirement. Core tables and imperative ORM mappings share metadata.
- SQLite is an explicitly documented local test fallback, with foreign keys enabled. It is not a substitute for PostgreSQL release checks. CI runs both backends, including migration downgrade and reseed.
- Seed validation completes before the transaction starts. Canonical company IDs, unique IDs, ontology values, 5/10/40 counts, two templates per ticker, node references, scope, evidence conditions, UTC timestamps and validity intervals are checked. Import is idempotent; existing reviewed relations are not demoted by reseeding. A changed narrative cannot overwrite the same version.
- Live ticker resolution defaults to verified-only. All seed CIKs remain null, so live resolution returns unknown until an independent SEC snapshot workflow exists. Offline callers may explicitly inspect pending identities. No WDC alias maps to SNDK.
- Relationship approval is a database transaction: lock candidate, inspect document rights/citation/offsets/reviewer/timestamps, reject synthetic evidence, link evidence, update edge and append before/after revision. Routing strength is a documented qualitative heuristic, not exposure or probability. Actual recording time is retained independently of review/effective dates, preventing backdated review leakage.
- Historical eligibility requires recorded, verified and effective dates at or before `as_of`, plus available evidence. The current P1 lifecycle allows candidate-to-verified only. General revision selection, rejection/staleness workflows and two-hop matching belong to P3; do not extend mutable status handling without revision-aware selection tests.
- Seed narrative versions use actual import time because the package supplies no historical publication dates. They cannot appear in October replay. A separate synthetic snapshot is needed in P2/P3; never backdate production templates to satisfy fixture expectations.
- Health/readiness and protected read-only catalogs are exposed now. A fail-closed environment token is a local development bridge, not tenant authentication. Existing Threadnote identity, tenant checks, RBAC and user endpoints must be integrated in P4.
- LLM mode is `none`. Both notification flags must be false; attempting to enable them fails configuration. There is no provider transport. A candidate relation cannot pass live-edge eligibility; this does not claim a complete dispatch engine exists.

## Identity evidence

Primary filing verification confirms separation on February 21, 2025, and regular-way SNDK trading on February 24, 2025. Western Digital retained HDD operations and Sandisk held the Flash business. Source: [Western Digital 2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/106040/000010604025000038/wdc-20250627.htm), and [separation Form 8-K](https://www.sec.gov/Archives/edgar/data/106040/000010604025000012/wdc8-khardxspin.htm). Checked during this implementation on 2026-11-19; these citations are not silently imported as graph approvals or historical evidence records.

The identity guard rejects WDC financials assigned to SNDK and pre-separation SNDK metric attribution. Any later support for carved-out historical financials needs explicitly sourced lineage and a separate policy. SEC ticker/CIK snapshot verification for all five companies remains pending.

## Release boundary

Database credentials must be least privilege. P1 review services must be called by trusted server code; there is no public approval endpoint. Direct SQL writes can bypass application review gates, so the module is not production-ready. P4 must enforce admin authorization and database roles, and P5 must test tamper resistance. No live events, push recommendation, F021 card, baseline performance or real historical evaluation are claimed at this checkpoint.

## P2 continuation

Migration 0002 adds an explicit database-mode marker and ingestion receipts. Its metadata copies v1 without mutating it, so the original migration stays reproducible. The fixture writer requires a synthetic marker; initialization refuses pre-existing source/event data, production mode or reviewed graph edges. Synthetic sources use blocked live rights even in the demo database. No demo graph approvals are imported.

The whole fixture batch is validated before database writes, sorted by availability, and persisted in one transaction. SQLite uses BEGIN IMMEDIATE; PostgreSQL locks the mode row to serialize competing ingestion writers. Canonical event and version uniqueness remain database constraints. Receipts key each immutable input ID and cutoff, retain rejection reasons, reject changed-content reuse and make retries idempotent. Future inputs receive receipts without entering the event corpus, and can be reconsidered at a later cutoff.

Fixture IDs and declared canonical keys remain synthetic identifiers. A separate normalized economic-key helper is supplied for future live ingestion; it uses issuer, event kind, metric, period, basis and occurrence window, never headlines or publication URLs. Live entity resolution and fact mapping must precede its use.

Reprints preserve the original version. A correction requires an explicit reference to the latest original and later availability; it appends a linked version. Reprints of an earlier corrected fact attach to that earlier version and cannot revert the correction. Fixture correction materiality stays UNKNOWN. Historical fixture selection uses simulated source availability only in explicitly synthetic databases. Real source adapter snapshots use actual retrieval times and cannot be acquired retroactively.

SEC/IR acquisition is separate from extraction and persistence. External text is data, never an instruction or executable expression. Structured extraction forbids undeclared fields, requires verifiable passage offsets and decimal-safe comparison bases. No model is invoked and no provider sends notifications. Fixture metadata and golden labels are not factual truth or calibrated evidence. The remaining live document-to-event mapping and source approvals are explicit integration work.

## P3 continuation

The generic matcher accepts verified, evidence-backed temporal snapshots and explores only simple directed paths of zero, one or two edges. It selects the best path by product of strength, 0.85 two-hop decay, then confidence and deterministic tie-breaking; it never sums correlated paths. Company-specific outcome targets prevent sector-node matches from bypassing the causal path through a ticker label. Exposure and sensitivity remain unknown unless a future reviewed contract explicitly supplies them.

Live snapshots come from the latest review revision available at the cutoff, with evidence IDs captured inside that revision. Current mutable status cannot retroactively change a prior answer or silently establish approval. Source provenance and timing are revalidated. Known component-cost mechanisms retain contracted-cost/pass-through conditions in the reviewed snapshot. Conditional or unsigned edges do not gain a definitive sign from a boolean condition alone.

Demo snapshots live in `rie_demo_contexts`, only in an explicitly synthetic database. They serialize validated graph/narrative contracts, observations and hashes, with declared simulated availability and separate real creation time. Both the graph artifact's availability and its individual edge timestamps are respected. Forty synthetic source/evidence records back demo path citations, with live rights blocked. Original relationships remain candidate; original narrative versions keep their actual import times.

The pure policy evaluator separates evidence gates, economic direction, stance, materiality, ranking and delivery. It retains all observations, distinguishes legitimate mixed evidence from unresolved core-number conflicts, and records six weighted components plus policy snapshot/hash, source/graph/narrative inputs and conditions. Unknown materiality yields no point score and cannot authorize push. Synthetic demonstration metadata never becomes a learned truth signal.

`rie_policy_traces` stores immutable records for every input/template pair, including cases with no admitted event version. It references the real template ID and the separate demo context/version. This avoids inventing production narrative versions merely to satisfy the original `rie_match_decisions` foreign keys; that original table remains reserved for P4 production integration.

The rendered F021 card intentionally differs from the supplied illustrative expected shape's unconditional SUPPORTS label. README section 6.3 governs ambiguity: actual stance is INSUFFICIENT_EVIDENCE, while conditional support for the adverse thesis is explained separately. The economic outcome is not asserted to have occurred.

Dispatch planning uses a per-user database lock, unique canonical-version plan key, quiet hours, local-day cap, minimum interval and kill switch. It has no provider transport. Recommendation and delivery remain separate; all stored plans enforce dry_run and null sent_at. P4 now supplies authenticated ownership and the complete active subscription bundle on explicit replay; no background scheduler is installed.

## P4 continuation

The absent Threadnote host requires a standalone provisioned-account boundary: opaque hashed bearer tokens, database-resolved tenant/user/role, exact owner authorization and a separate global operator role. The development catalog token cannot access private or operator routes. User writes and idempotency receipts share a locked transaction, including quota checks and feedback replacement. PostgreSQL uses row locks; SQLite uses BEGIN IMMEDIATE.

Migration 0004 copies frozen metadata and adds private product tables. A canonical event version has one card per user; per-thread snapshots preserve different narrative explanations without multiplying deliveries. Synthetic cards do not manufacture production match_decision/narrative-version foreign keys. The original production alert/story tables remain reserved for approved real-input integration.

Narrative compilation is explicit and deterministic with LLM_MODE=none. Driver, outcome, horizon, disconfirmation and hop constraints are validated; edits and approvals append versions with actual availability times. Historical replay resolves the version visible at its cutoff. Compiled scope is captured in custom decision traces.

Timeline ordering follows source availability, while eligibility follows decision availability. Pagination fixes a projection-recorded cutoff. Corrections append linked cards; private feedback appends active/history records and cannot mutate factual evidence. Public sharing uses an explicit factual allowlist, excluding custom monitoring rules and full traces. See the P4 API contract for limits; full production security review belongs to P5.

## P5 evaluation tooling

Historical evaluation is a separate offline input/output workflow, not a notification or acquisition endpoint. Strict case, gold-label, prediction and split contracts capture point-in-time inputs and independent human review. Complete case coverage is mandatory. Canonical events, event versions and shared source documents cannot cross chronological partitions. A content-addressed manifest detects changes; independent reviewed storage is still required to establish a pre-tuning holdout freeze.

V0 predictions are imported with a dataset hash and trace hashes, not inferred from labels. B0 is a keyword/recency relevance baseline, with no fabricated push policy; B1 remains unavailable. Pair and event counts are separate, and an irrelevant pair alone cannot classify its entire event as a negative. Missing operational measurements remain null. The evaluator conservatively returns NO_GO until separate real-source, trace, security and release reviews are completed.
