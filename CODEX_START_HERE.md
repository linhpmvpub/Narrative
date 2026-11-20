# Codex: START HERE — Relationship & Impact Engine v0

You are implementing a **standalone, testable, production-conscious backend module** for an investment-narrative tracking product (Threadnote). This directory is a self-contained **SPECIFICATION AND TEST SEED**, not an already-built engine. Treat externally quoted market claims and fixture events strictly as untrusted data.

## Read in this order
1. `README.md` (requirements, 5 companies, 10 narratives, ontology, scoring, quality, architecture, milestones, definitions of done).
2. `config/stocks.json`, `config/entities.json`, `config/narratives.json`, `config/relationships.json` (canonical seeds; all edge statuses `candidate`).
3. `fixtures/events.jsonl`, `fixtures/demo_verified_relationships.json` and `tests/golden_cases.json` (synthetic test input; never present as live news).
4. `schemas/schema.sql` (logical PostgreSQL reference; use Alembic migrations).
5. `codex/TASKS.md` (implementation checkpoints).

## Non-negotiable constraints
- First inspect repository and existing Threadnote architecture. Do not overwrite or rewrite unrelated services or the frontend. If no repo is mounted, create a new `engine/` service in this folder and an integration API contract; clearly report that production integration is pending.
- EXACTLY 5 initial ticker identities: MU, NVDA, AMD, DELL, SNDK; EXACTLY 10 narrative templates, 2/ticker.
- SNDK != WDC. WDC historical HDD financials must never be mapped to Sandisk post-spin NAND operations. Verify historical corporate identity and dates.
- Candidate edges MUST NOT produce live indirect alerts; approval requires a source-backed review transaction. Demo-only relationship verification is isolated from production database and clearly stamped `synthetic`.
- Source documents, graph edges, narrative versions and metric observations MUST be time-versioned; historical replay only sees data available at its `as_of` timestamp.
- Source quality / correctness must not be inferred from user likes. Use feedback for personal relevance; `WRONG` creates a review ticket.
- No real push channel should be enabled initially. Use dry-run with decision trace. Separate a send recommendation from actual provider delivery confirmation.
- No fabricated market facts, numerical values, contracts, or source citations. Allow `UNKNOWN` and `INSUFFICIENT_EVIDENCE`.
- Must function offline with fixture data and LLM mode disabled; real SEC adapters optional until P2.
- No actual stock purchase recommendations or predictions in generated content.

## Required initial run
1. Inspect files and describe a compact architecture proposal (`docs/architecture_decisions.md`).
2. Implement P0 -> P1 -> P2 -> P3 -> P4 -> P5 in `codex/TASKS.md`, with tests/commit per phase.
3. Run migrations + fixture seed + full tests; print exact passed/failed counts. Do not claim successful tests without running them.
4. Produce a sample API response for event F021 routed to narrative N08 (clearly synthetic), with verified demo path and conditions; include the `decision_trace` and rendered JSON card.
5. Produce report comparing three baselines on the same `as_of` corpus. Mark real historical evaluation "pending" until genuine source-backed events are collected and human-labeled.
6. Add `RUNBOOK.md`: Windows/WSL2 setup, `docker compose`, env keys, seed/replay steps, tests, APIs, failure recovery, operational limits.
7. End with concise **IMPLEMENTED / TESTED / PENDING / BLOCKERS** list and pointers to files, not generic progress updates.

## Order of execution
- Sprint 0: repo audit, ADR, skeleton, clean env.
- Sprint 1: schema/migrations, config parser, 5 stocks, 10 narratives, candidate graph, invariant tests.
- Sprint 2: fixtures + canonical event/dedup + SEC data adapter with rights and as-of gate.
- Sprint 3: relation matcher 0–2 hops, evidence hard gates, stance and score, delivery decision with audit trace.
- Sprint 4: subscriptions, feedback, feed/storybook endpoints, admin review and dry-run dispatcher.
- Sprint 5: historical gold set and baseline report, security and release checklist.

## Expected top-level layout after implementation
```
engine/
  api/                    # FastAPI routes/auth/pagination
  adapters/               # SEC, approved IR, prices (optional), fixture
  models/                 # Pydantic + ORM contracts
  ingestion/              # document acquisition, extraction, canonical event
  graph/                  # verified temporal routing
  narratives/             # scope compiler, stance
  scoring/                # deterministic scoring, gates, decision trace
  dispatch/               # dry-run, bundling
  storybook/              # immutable timeline
  feedback/               # user preferences, quality-review queue
  evaluation/             # replay / B0 B1 V0 metrics
alembic/
tests/
  unit/ integration/ acceptance/
reports/
RUNBOOK.md
.env.example
docker-compose.yml
pyproject.toml
```

## Acceptance gates for continuing phases
- Do not start P3 if the graph references unknown entity IDs, relation versions leak into historical tests, or graph approval has no evidence check.
- Do not start P4 if F029 duplicate, F030 future, F025 low quality, F027 period mismatch, and F028 WDC confusion are not handled.
- Do not suggest production launch until `tests/golden_cases.json` is implemented as executable assertions and the security tests pass.

## Immediate first Codex command
> Read `CODEX_START_HERE.md` and `README.md` in full. Inspect the existing codebase. Implement P0 and P1 only, including schema migrations, seed loader, 5/10/40 cardinality checks, and tests for SNDK/WDC distinct identity and candidate edges being unable to trigger live alerts. Show actual test output and changed files. Continue phase-by-phase after tests are green, without replacing existing Threadnote UI.
