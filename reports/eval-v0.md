# Evaluation v0 — historical run pending

P5 offline dataset/label validation and metric tooling is implemented. No approved real historical corpus or independent human labels have been supplied: **0 historical events evaluated**. Historical push precision, material recall and two-hop recall are unavailable, not zero or perfect.

Use `docs/historical_evaluation.md` and `evaluation/historical-v0/` to collect and freeze the corpus before tuning. The CLI evaluates B0 and submitted V0 on identical complete case sets with chronological partitions, counts, denominators and descriptive confidence intervals. B1 remains UNAVAILABLE because LLM mode is disabled. Exact source/trace authenticity and pre-tuning holdout freeze require independent review.

Existing `reports/p3-baselines.json` is synthetic: 30 eligible inputs / 300 template pairs at 2026-11-01T00:00:00Z; 8 B0 matched pairs and 56 V0 verified-path pairs. These are routing counts, not evidence of historical accuracy or improvement.

**Release decision: NO_GO.** Real historical acquisition/labels, deployment security validation, actual Threadnote integration and PostgreSQL runtime validation remain pending. The scoped local source-level threat review and fixes are recorded in `reports/p5-security-checkpoint.md`; this is not external security certification. Notifications remain disabled.
