# Cost and latency v0 — measurement pending

No historical acquisition or model API run was performed for this tooling task. Total operating cost, cost per real event and production p95 latency are **unavailable**. No zero-cost production claim is made.

Prediction contracts accept measured `latency_ms` and `cost_usd`, reject negative/non-finite values, and report measurement coverage. p95 uses nearest rank over observed measurements. Total cost is null unless all evaluated predictions supply a measurement. B0 matching output has no fabricated timing or cost samples.

LLM mode remains disabled, B1 unavailable, and no live notification provider is configured. SQLite test duration is regression-test runtime, not production event latency. A real benchmark must record acquisition, extraction, matching, queueing and infrastructure costs separately and define their accounting boundaries.
