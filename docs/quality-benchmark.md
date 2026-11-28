# Continuous local quality benchmark

The user requested a benchmark after every system, relationship database or algorithm
update (2026-11-28). `engine.evaluation.benchmark` replaces one-off replay scripts for
ongoing regression measurement. It runs the actual current routing and editorial
priority code against immutable news/narrative targets. It never sends notifications,
uploads data, changes a production registry or authorizes release.

## What is measured

- Narrative relevance: TP/FP/TN/FN, precision, recall, unresolved and selected
  unresolved pairs; positive/negative/selected-positive event-cluster support.
- Editorial priority: the same metrics against **priority labels**, not relevance
  labels. Cohorts without priority labels explicitly remain unmeasured.
- Cohort, event group (including unknown) and company breakdowns. RSS excerpts,
  full articles and issuer archives stay separate. Multiple group memberships
  and correlated narrative pairs must not be added into a market accuracy score.
- Every changed decision versus a pinned prior run, including improvements,
  regressions and unresolved changes. A net gain cannot hide a lost positive or
  newly selected negative. Priority gains cannot hide relevance failures.
- Source, label, target, runtime/config and profile-registry integrity. A current
  benchmark is not proof that its quality meets product acceptance.

Financial magnitude, short/long company impact horizon, causal truth, personalized
utility, live coverage/latency and fresh blind generalization are **not measured** by
this reference. Keep their acceptance checks separate; never infer them from a high
relevance score or a passing test suite. See [v1 acceptance](product-v1-acceptance.md).

## Versioned inputs and immutable runs

The local spec contains `version`, timezone-aware `as_of`, `limitations` and cohorts.
Each cohort declares `id`, normalized `rows`, original `provenance` files and an
optional dedicated `article_dir`. A normalized pair contains unique `id`, `ticker`,
`groups`, `event_cluster`, `label`, nullable `priority`, `track` and `input` (original
article, profile ID, narrative target and source observation/archive identity).

Before importing existing references, verify original packet/freezes, reviewer
hashes, consensus, full-body receipts and target equality. Retain this migration
receipt locally. `create` pins normalized inputs **and** their provenance and full
article caches. It does not independently certify the truth of imported labels.
Do not use a continuously growing live article cache as a frozen cohort cache.

`run` validates complete current profiles and source evidence, re-executes matches,
rejects changed narrative targets, and checks runtime/database/source pins again
before publishing results. A new output directory is required. Run receipts pin
predictions, reports and the prior receipt. Separate processes should run each
version; runtime policy caches are process-local.

Inputs remain fixed, but profiles are replayed at the run's UTC time, or explicit
`--as-of`. A later database version can therefore be evaluated without pretending
it was known at the article's publication. Reports retain both replay times; use
the same `--as-of` when isolating code-only effects, and inspect temporal eligibility
changes when comparing later database versions. This is not a historical backtest.

```powershell
$env:PYTHONPATH='.'
$env:DEV_INFORMATIONAL_FEED='true'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/python.exe -m engine.evaluation.benchmark create --spec LOCAL_SPEC --suite LOCAL_SUITE
.venv/Scripts/python.exe -m engine.evaluation.benchmark run --suite LOCAL_SUITE --suite-sha256 PINNED_SHA --profiles LOCAL_PROFILES --output NEW_RUN --baseline PREVIOUS_RUN
.venv/Scripts/python.exe -m engine.evaluation.benchmark check --suite LOCAL_SUITE --suite-sha256 PINNED_SHA --profiles LOCAL_PROFILES --output NEW_RUN
```

`check` fails on changed runtime/config, profiles/pointers/sources, labels, corpus or
run outputs. A missing/failed/stale run blocks a claim of completed validation.
It checks the recorded replay instant, not continuous wall-clock freshness.
No automatic gate enables live delivery. Regression costs require written review;
do not silently replace the baseline until those costs are recorded.

## Development loop after every update

1. Read direction, principles, workflow and checkpoint. Record the shared failure
   class and expected investor benefit. Verify the previous benchmark before edits.
2. Change data or common logic, preserving source/version and target semantics.
   Never add ticker/headline exceptions to improve the benchmark.
3. Run relevant software tests, then the full local benchmark against the previous
   immutable run. Review every changed decision and group/company regression.
4. Run `check` after the **last** runtime/database edit; update the local current-run
   pointer, checkpoint and quality review. Preserve all failed/superseded runs.
5. Run repository CI on the code commit. Publish code/synthetic tests/docs and a
   sanitized aggregate only; private inputs, labels, article bodies and predictions
   remain in ignored `source-cache`. CI tests benchmark integrity on synthetic data;
   it cannot run the private market corpus.
6. Add unused event families and independently blinded labels in a new suite
   version when needed. Keep old suites for regression and version comparison.

This is an update-triggered development gate, not a scheduled/background service.
The repository's `.githooks/pre-commit` invokes the freshness gate for staged engine,
config or dependency changes. Install with `git config core.hooksPath .githooks`
only after checking for an existing hook configuration. It rejects a missing/stale
local pointer and differing staged/worktree runtime. Documentation-only commits
do not rerun the corpus. Git hooks are local and can be bypassed; they are not a
remote enforcement/security boundary. Database-only updates must also run:

```powershell
.venv/Scripts/python.exe -m engine.evaluation.quality_gate --all
```

The ignored `source-cache/quality-benchmark-current.json` contains `suite`,
`suite_sha256`, `profiles` and `run`. Updating this pointer never edits old runs.
The hook verifies freshness, not product acceptance or reviewer approval.

Repeatedly exposed AI labels are development references, not fresh blind or human
gold. Avoid tuning weights until the cohort support and feature evidence justify
it; measure false promotions and missed developments separately.
