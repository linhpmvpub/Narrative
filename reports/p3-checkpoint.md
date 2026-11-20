# P3 checkpoint — 2026-11-19

## IMPLEMENTED

- Directed zero/one/two-hop matching over verified temporal edge snapshots. Unknown nodes, cycles, candidate/rejected/stale edges, missing evidence, expired validity and future approvals cannot establish a route. Alternative paths are retained; only the strongest path contributes relevance, using the product of strengths and 0.85 two-hop decay. Confidence is separate and uses the minimum source/edge confidence.
- Production snapshots come from audited relationship revisions with captured evidence IDs, not mutable current status. Tests show that a later rejection does not rewrite an earlier approved view, and that a directly edited verified row without review cannot route. Component-cost reviews retain contract and pass-through conditions.
- Immutable, explicitly synthetic graph/narrative contexts with source hashes and simulated availability. Snapshot headers and individual edges are both time-gated. The original 40 relationship rows remain candidate, and production narrative versions retain their real import times.
- Deterministic evidence/identity/rights/time/novelty/period/conflict gates, stance semantics and the exact six-feature v0 score. Unknown materiality remains null, with optional score bounds rather than an invented impact magnitude. Adverse-thesis support maps to an adverse economic implication, never a stock-price prediction. Unsupported direction and conditions remain insufficient evidence; countervailing observations can produce MIXED.
- Immutable traces for every fixture/template pair, including suppressed and pre-ingestion-rejected inputs. Traces include inputs/hashes, context/narrative versions, policy snapshot/version, gates, selected and alternative paths, observations, conditions, score components, evidence and delivery state.
- Dry-run dispatch planner with per-user bundling, canonical-version deduplication, quiet hours, local-date daily cap, minimum interval and kill switch. Recommendations are distinct from delivery. There is no provider transport; sent_at remains null. Synthetic plans cannot be delivered even with the kill switch lifted.
- Working replay CLI, rendered synthetic F021/N08 JSON response, and an as-of baseline comparison. No user-facing admin route or production authentication shortcut was added.

## TESTED

Actual final command:

```text
.\.venv\Scripts\python -m pytest -q -o faulthandler_timeout=20 --junitxml=reports/p3-tests.xml
128 passed, 1 warning in 55.28s
```

**128 passed / 0 failed / 0 skipped**, including 82 prior tests and 46 new P3 tests. Windows, Python 3.13.7, isolated virtual environment, SQLite. Windows loopback permission was required for the API test client; external source requests remain mocked or blocked. The single warning is the existing Starlette/httpx test-client deprecation.

Also executed successfully:

```text
python -m ruff check engine alembic tests
All checks passed!
python -m mypy engine
Success: no issues found in 29 source files
python -m pip check
No broken requirements found.
python -m alembic upgrade head
python -m engine.seed --config config
5 stocks / 42 entities / 10 narratives / 40 candidate relationships
```

Migration 0003 was applied to an existing demo database and a fresh validation database. The test suite exercises migration upgrade/downgrade on disposable databases. The original 15 handoff files remain unchanged against their manifest.

The final CLI was run twice against `sqlite:///rie-p3-validation.db`:

```text
python -m engine.ingest --demo --initialize-demo --as-of 2026-11-01T00:00:00Z
python -m engine.replay --dry-run --as-of 2026-11-01T00:00:00Z --output reports/p3-replay.json --sample-output reports/p3-F021-N08.json --baseline-output reports/p3-baselines.json
python -m engine.replay --dry-run --as-of 2026-11-01T00:00:00Z
```

Both replay runs returned identical counts: **310 decisions: 76 review_required, 232 suppressed, 2 storybook**. The database still contains 310 traces, 0 alerts and 0 dispatch plans. No fixture has verified numeric materiality, so no push or digest recommendation was invented. Dispatch planning with fully specified test inputs is covered separately by unit/integration tests.

## Generated F021 / N08 response

Artifact: `reports/p3-F021-N08.json`, containing the actual computed `decision_trace` and rendered `card`.

```text
SYNTHETIC NAND_ASP
  -- R026, SUPPLIER_COST --> SERVER_COMPONENT_COST
  -- R027, FINANCIAL_TRANSMISSION --> DELL_ISG_MARGIN
```

| Field | Computed result |
|---|---|
| Actual stance | INSUFFICIENT_EVIDENCE |
| Conditional stance | SUPPORTS |
| Actual economic effect | UNCERTAIN |
| Conditional economic effect | ADVERSE_IF_CONDITIONS_HOLD |
| Decision | review_required |
| Relevance | 0.6 × 0.6 × 0.85 = 0.306 |
| Path confidence | 0.90, separate from relevance |
| Components R/M/N/Q/T/U | 0.306 / null / 1 / 0.96 / 0.5970618859852485 / 1 |
| Point score | null: materiality unknown |
| Score bounds | 58.021–78.021, not probabilities |
| Conditions | Contracted cost actually rises; pricing/rebates/mix do not offset it |
| Delivery | disabled; sent_at=null |
| Policy version | rie-v0.3-1d21ff630906 |

The cited fixture event and both synthetic edge-evidence URLs resolve to synthetic database documents. Exposure, sensitivity, numerical impact and realized company outcome are not invented.

The supplied expected-shape fixture says unconditional SUPPORTS; the governing README requires INSUFFICIENT_EVIDENCE when conditions are unverified. The generated response follows that rule and displays conditional support separately. Original expected fixtures were not rewritten to hide this distinction.

## Baseline comparison

Artifact: `reports/p3-baselines.json`. All variants are scoped to the same **30 available inputs / 300 template pairs** at 2026-11-01T00:00:00Z. F030 is excluded from this comparison but retained as ten suppression traces in the full replay.

| Variant | Result | Interpretation |
|---|---|---|
| B0 ticker keyword + 30-day recency | 8 matched pairs | No evidence gates; includes the WDC/SNDK confusion fixture |
| B1 direct ticker + LLM | UNAVAILABLE | LLM_MODE=none; no replacement presented as an LLM baseline |
| V0 graph + gates | 56 verified-path pairs | 76 review_required, 222 suppressed, 2 storybook across the 300 eligible pairs |

These are descriptive routing counts, not push precision, material recall or proven improvement. Precision/recall remain null. **Real historical evaluation is pending genuine source-backed, human-labeled events and a frozen holdout.**

## PENDING / BLOCKERS

- PostgreSQL runtime validation remains blocked by the unavailable Docker Linux engine (`dockerDesktopLinuxEngine` pipe missing). PostgreSQL CI is configured, including ingestion/replay smoke commands, but no remote CI run is claimed. Local tests use SQLite.
- Real SEC identity verification, source approvals, live document-to-event mapping and calibrated metric-specific materiality remain pending. Generic scoring contracts require validated inputs; they are not a public endpoint accepting untrusted assertions.
- P4 still owns authenticated subscriptions, user/tenant authorization, feed/story APIs, feedback and scheduler integration. The planner expects all matching threads in one batch; authenticated subscription gathering is not implemented here. Synthetic traces intentionally use the new audit table, rather than fake production narrative versions in `rie_match_decisions`.
- P5 still owns the full security/release review and historical evaluation. Remaining golden assertions such as story correction links, feedback behavior, custom narrative entitlements and private sharing are not claimed complete.
- Legacy approved edge revisions lacking captured evidence IDs fail closed in the new snapshot loader; any migration must be reviewed rather than reconstructing historical evidence links from today's database.
- The actual Threadnote repository/auth contracts and Git author configuration remain unavailable. No phase commit was created in this non-Git handoff folder. No production launch is recommended.

## Changed files and artifacts

Added: `engine/graph/matcher.py`, `engine/graph/demo.py`, `engine/scoring/`, `engine/dispatch/`, `engine/evaluation/`, `engine/replay.py`, `engine/models/schema_v3.py`, `alembic/versions/0003_policy.py`, `fixtures/p3_demo_policy.json`, and `tests/test_policy.py`, `tests/test_dispatch.py`, `tests/test_graph_temporal.py`.

Updated: `engine/graph/review.py`, `engine/api/__init__.py`, `alembic/env.py`, `.github/workflows/ci.yml`, `RUNBOOK.md`, `docs/architecture_decisions.md`, `docs/integration_api.md`.

Evidence: `reports/p3-tests.xml`, `reports/p3-ingestion.json`, `reports/p3-replay.json`, `reports/p3-F021-N08.json`, `reports/p3-baselines.json` and this checkpoint.
