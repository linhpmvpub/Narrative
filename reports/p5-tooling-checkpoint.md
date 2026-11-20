# P5 evaluation tooling checkpoint

## IMPLEMENTED

Implemented the next offline P5 task after the P4 checkpoint: strict historical case, human-label, prediction and chronological-split contracts; source/rights/narrative/edge/metric availability checks; immutable corpus manifests; complete-case coverage checks; same-corpus B0/V0 evaluation with B1 explicitly unavailable; confusion counts, material-pair and two-hop recall, descriptive Wilson intervals, per-ticker holdout summaries, disagreement records and measurement coverage.

Canonical events, event versions and identical source documents cannot cross chronological partitions. Events and narrative pairs have separate denominators. An irrelevant pair does not turn an otherwise positive event into a negative. Zero denominators and missing operational measurements remain null. Labels are separate from policy inputs, and no human judgments are inferred from synthetic expectations.

CLI commands: `python -m engine.evaluation.cli init`, `freeze`, `label-template`, `evaluate`. Outputs refuse overwrite. Prediction envelopes bind the frozen dataset hash; label/prediction inputs must cover the full corpus. Existing notification/LLM settings guards remain in force.

Added `engine/evaluation/historical.py`, `engine/evaluation/cli.py`, `tests/test_historical_evaluation.py`, `docs/historical_evaluation.md` and an empty `evaluation/historical-v0/` workspace with four matching JSON schemas. Published explicit pending-state `reports/eval-v0.md`, `reports/quality-errors.md`, `reports/cost-v0.md`; updated runbook and architecture decisions.

## TESTED

- Focused evaluation tests: **21 passed**. Covers future inputs, mode separation, cross-split contamination, frozen content changes, missing/extra/duplicate coverage, zero denominators, evidence mismatch, policy mixing, CLI artifact preservation, unfilled label templates, event-versus-pair counting and invalid measurements.
- Ruff: all checks passed. Mypy: no issues in **36 source files**.
- Final full regression run: **167 passed**, 0 failed, 0 skipped, one upstream Starlette/httpx deprecation warning, **92.80 seconds** on Windows/Python 3.13 with temporary SQLite databases. Command: `.\.venv\Scripts\python -m pytest -q -o faulthandler_timeout=20 --junitxml=reports/p5-tooling-tests.xml`. Local loopback permission was used for TestClient; external network access is blocked by the test fixture.
- Verified all four exported schemas equal their implementation schemas and `cases.jsonl` is empty. CLI initialization and freeze/template/evaluation flows are exercised offline.

## PENDING / BLOCKERS

**0 real historical events evaluated.** Acquisition through approved sources, genuinely archived source/graph/narrative/metric snapshots, independent human labels and a reviewed pre-tuning holdout freeze remain pending. No network acquisition or paid API call was made in this task.

The evaluator validates submitted metadata and hashes; it does not authenticate archives, approve licenses, recompute arbitrary trace hashes or prove when a holdout was frozen. An exporter for actual real-source policy results and independent trace/source review are still required. Cost/latency require recorded measurements; factual errors, duplicate deliveries, weekly alert rates and reviewer agreement require additional reviewed records.

P5 security/threat review and release assessment are not complete. PostgreSQL runtime validation was blocked at the prior checkpoint by Docker's missing Linux engine; it has not been revalidated in this offline-tooling task. Threadnote integration and Git phase commits remain pending the previously unavailable host repository/configuration.

**NO_GO for production.** Live notifications remain disabled. The next data-dependent task is approved historical corpus collection and independent labeling; the next independent engineering task is the P5 threat/security review.
