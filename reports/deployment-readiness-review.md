# Deployment readiness review — 2026-11-28

Added sourced AMD customer-buildout and MU manufacturing-utility mechanisms and an opt-in shared resource-context contract. Numerical weights, source bytes, narrative targets and labels are unchanged. Raw inputs, profiles, DB, labels, predictions and card traces remain local.

## Step-by-step measurement

| Step | Improvements | Regressions | Unresolved changes |
| --- | ---: | ---: | ---: |
| step1 | 0 | 0 | 0 |
| step2 | 4 | 1 | 0 |
| step2-final | 1 | 0 | 0 |
| final | 0 | 0 | 0 |

Step1 adds graph data without changing selections. Step2 recovers four relevant pairs but also confuses component power efficiency with utility capacity in one prior negative. Step2-final binds the condition to the actual resource, removing that regression without losing the four recoveries. Final repeats the hardened result. Initial failures/runs are retained.

Cumulative versus the original task baseline: **4 relevance improvements, 0 measured regressions, 0 unresolved decision changes; no priority changes**. These are now-exposed AI references, not fresh blind or human-gold validation. No pooled market accuracy is claimed.

## Cohort outcomes

| Cohort | Relevance TP/FP/FN before → after | Priority TP/FP/FN after |
| --- | --- | --- |
| framework121 | 31/0/17 → 31/0/17 | 9/0/19 |
| actor77 | 6/0/6 → 6/0/6 | 3/0/2 |
| rss120 | 8/0/4 → 8/0/4 | 6/0/3 |
| infra160 | 9/0/14 → 13/0/10 | 5/0/4 |
| memory-unseen-2026-11-27 | 25/0/13 → 25/0/13 | 9/0/23 |
| priority-blind-2026-11-26 | 5/0/2 → 5/0/2 | 5/0/0 |
| priority-issuer-archive-2026-11-26 | 2/0/0 → 2/0/0 | 2/0/0 |
| older-rss | 54/3/42 → 54/3/42 | NOT_MEASURED |
| older-archive | 5/0/7 → 5/0/7 | NOT_MEASURED |
| older-full_article | 25/1/3 → 25/1/3 | NOT_MEASURED |

The infra160 relevance recoveries are AMD deployment context (3) and MU manufacturing utility context (1). Relevance unresolved20 and priority unresolved21 are unchanged;10relevance/4priority misses remain. Other cohorts are unchanged. Complete aggregate group/company metrics are in the companion JSON. Three old cohorts lack priority labels; do not use relevance as a proxy.

## Local pipeline and verification

Six profiles,84nodes,101relations,11narratives. Four added relations comprise two exposure edges and two mechanisms. Existing4commodities/7input exposures/2price markets/3market links remain. Financial selection versions for changed profiles were revalidated against unchanged source bytes and figures.

RSS poll:10attempts,7OK/3NOT_MODIFIED,0created/updated. Isolated pipeline:50main/45background,0price alerts,no truncation. Three current-feed cards carry the new context trace; all stay background/sponsored. All95cards have delivery disabled and financial direction/magnitude/horizonUNKNOWN. This is a snapshot, not a7day reliability or newly acquired event test. Default server/database/tunnel untouched; no new browser acceptance claim.

Final focused tests:157passed,1existing Starlette warning,72.43s. Ruff and mypy171passed. Benchmark freshness gate current. Exact-code CI[46121885998](https://github.com/linhpmvpub/Narrative/actions/runs/46121885998)SUCCESS on3b06d6f: 1752 passed, 1 warning in 171.57s (0:02:51); 1752 passed, 1 warning in 304.92s (0:05:04); JS,migrations/seed/replay/downgrade,both dependency audits and actual-model smoke8passed.

## Limitations and next step

The matcher deliberately does not attribute a facility incident, customer order, supplier identity or quantified effect to the profiled company. DELL utility/construction scope still needs primary evidence. NVIDIA demand-side scope is not silently converted into supply scope. Bounded English phrases can miss coordination, implicit references and title/body connections.

One sponsored current-feed description supplies general facility power context although its headline concerns an audit; it has no independent label and is not credited as a quality gain. Next improve primary-event versus descriptive boilerplate scope and source-actor/asset references as shared contracts, then measure group-level recall/precision on unused event families. Do not fix with ticker/headline exceptions.

Causal truth, magnitude/horizon, personalized usefulness, fresh generalization and live coverage/latency remain unmeasured. Existing older false positives and unlabelled priority changes remain open. Product acceptance unchanged; v1 not released; cloud and live notifications remain off.
