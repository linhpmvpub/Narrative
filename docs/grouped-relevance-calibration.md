# Grouped relevance calibration — 2026-11-26

The user activated comprehensive evaluation after the bounded core implementation.
The product objective remains source-grounded, explainable news discovery across company
relationships, rather than stock forecasting. This pass audits existing independent AI
references and searches an offline relevance-selection candidate. It does not establish
push utility, causal effect, financial magnitude or impact lag.

## Evidence and split

Nineteen previously exposed cohorts contain2,499article/narrative pairs. Their original
packet/prediction digests and consensus provenance are checked by the existing evaluator.
333pairs are excluded because the full frozen narrative does not equal a current target.
The remaining2,166pairs form398conservatively connected clusters. RSS:1,716pairs/308clusters;
archive:300pairs/75clusters; full-body:150pairs/15clusters, audited under their original
predictions only. No replacement labels were authored. The two-agent AI labels are not
human gold, and prior declared independence is not a new independently verified review.

Before reading labels, the local plan freezes cohort names, exclusions, split, candidate
grid, objectives, current source-validated profile hashes, policy, runtime and predictions.
Clustering unions same frozen event IDs, canonical URLs, archive source hashes/issuer-period
keys, identical text and >=0.8trigram overlap transitively. All narratives in a component
stay together. This can overmerge shared boilerplate and miss semantically equivalent news;
it is not a verified economic-event taxonomy.

SHA256(component ID) modulo10 assigns0–6to calibration and7–9to development validation.
RSS split:1,144pairs/209clusters vs572pairs/99clusters. Both sides were previously exposed
to development. **This is not a new blind holdout**, even though the current candidate is
chosen without validation labels. RSS, archive and full-body results are not pooled.
Current-profile replay bypasses feed freshness and ingestion eligibility; it is not an
as-of historical replay or a measurement of delivered-feed precision.

Seven fixed lexical multi-label topic strata plus other are assigned from source text,
not predictions. They can overlap; summing their counts double-counts stories. They are
coverage/error-analysis strata, not verified causal mechanisms. Calibration inspection found
financial-services technology-adoption language can enter the financing stratum; this is
a topic-classification limitation, not evidence of a funding event. Preserve the declared
strata for this report; future mechanism-specific calibration needs reviewed event types.
Changed company evidence
can also change interpretation despite exact narrative equality; scope equality alone
does not make old labels a current gold standard.

## Findings

| RSS stage | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Shared routing primitives |54|4|42|93.1%|56.3%|
| Current priority selection |19|1|77|95.0%|19.8%|

258/1,716pairs(15.0%) are unresolved and excluded from precision/recall, never treated as
negative. Selected unresolved counts are11for routing and6for priority. There are58positive
RSS clusters; pair counts are correlated. The priority rule suppresses35resolved relevant
pairs already found by the database routing path. They may still be visible in the background
section; this is not evidence that all35were dropped from the complete feed. Absence of directional change language
is therefore not a reliable proxy for absence of informational relevance. Some references
include broad/educational context: this does not imply all should become important alerts.

| Topic | Positive clusters | Routing TP/FP/FN | Routing recall |
|---|---:|---:|---:|
| Supply/disruption |4|8/0/5|61.5%|
| Input prices/costs |10|10/1/9|52.6%|
| Capacity/deployment |25|26/1/16|61.9%|
| Demand |9|10/0/9|52.6%|
| Technology |14|10/1/18|35.7%|
| Financing |8|6/1/6|50.0%|
| Policy |2|2/0/1|66.7%|

Every group misses the predeclared80%recall target; several also lack positive clusters.
AMD/MU each have only2resolved positive pairs and0TP. SNDK has0resolved positive references,
so recall is undefined. DELL:13TP/1FP/17FN; NVDA:41TP/3FP/21FN. Do not infer five-company
readiness from the better supported DELL/NVDA slices. Archive routing has5TP/0FP/7FN and
only8positive clusters; priority selects no resolved positives. Archive scope does not
justify transferring that result to current RSS delivery.

## Calibration result and deployment decision

The finite grid varies resolved-entity/change/sourced-path/sponsorship coefficients and
thresholds. Only RSS calibration rows enter selection. Objective: maximum recall at
precision>=85%, with at least10selected positive clusters; ties prefer weights closest
to the baseline and then the lower threshold. Hard sponsorship exclusion and existing
source-bound matching remain intact. No article-specific exceptions are introduced.

Selected offline candidate retains40/30/20/20weights and uses threshold20: effectively
include all matched, non-sponsored context. Calibration:31TP/2FP/32FN,93.9%precision,
49.2%recall. Development validation:23TP/2FP/10FN,92.0%precision,69.7%recall, compared with
current priority11TP/1FP/22FN,91.7%precision,33.3%recall. Validation has90unresolved pairs;
the candidate selects2of them. No independent accuracy uplift is claimed.

**Production policy stays unchanged.** Recall is below even the product70%target and
below the group80%target. These data are exposed and do not measure editorial importance.
The sourced-path feature is constant on eligible cards and sponsorship is a hard rule;
multiple coefficients/thresholds produce identical selections. The retained coefficients
are not identifiable estimates of relationship strength. Numeric impact/lag labels are
absent. No magnitude, probability or horizon is filled from these relevance scores.
The commodity >5%/>=10%gates are unchanged engineering thresholds: the input-price topic
slice is not a benchmark of normalized commodity alerts. Two real price observations do
not support calibrating those thresholds or the7/30day windows.

## Reproduce locally

`engine.evaluation.grouped_relevance` provides prepare/evaluate CLI stages. Use a new
output directory for each freeze/analysis. Detailed packets, features, labels and errors
stay in ignored `source-cache/grouped-calibration-2026-11-26`; the aggregate public-safe
report is `reports/grouped-relevance-calibration.json`.

```powershell
$env:PYTHONUTF8='1'
$env:DEV_INFORMATIONAL_FEED='true'
$env:NEWS_ARTICLE_DIR='source-cache/full-article-2026-11-24/articles'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/python -m engine.evaluation.grouped_relevance prepare --directory source-cache/NEW-FREEZE --plan source-cache/grouped-calibration-2026-11-26/plan.json --profiles source-cache/financial-context-2026-11-24/profiles
.venv/Scripts/python -m engine.evaluation.grouped_relevance evaluate --directory source-cache/NEW-FREEZE --output source-cache/NEW-ANALYSIS
```

The explicit article capture root is necessary to recheck the older full-body packet.
Missing source artifacts fail verification; do not turn off that check to obtain metrics.

## Next improvement cycle

1. Preserve this corpus as regression and its excluded event/issuer periods. Collect a
   fresh cohort with AMD/MU/SNDK positives and policy, supply and finance coverage; audit
   event grouping independently. Maintain original acceptance targets.
2. Label informational relevance separately from priority/novel development. Test whether
   broad source-grounded context belongs in a visible secondary feed rather than equating
   all relevance with a main alert. Do not infer priority preferences from relevance votes.
3. Diagnose unmatched relevant groups in database scope, entity resolution and extraction;
   change reusable factor/rule classes on calibration data only. Freeze the candidate,
   obtain independent reviews in separate contexts, then score the untouched holdout once.
4. Calibrate relation strength/lag only when their own source-supported reference dimensions
   exist. Keep unknowns explicit. No cloud/service changes or real notifications follow
   automatically from any benchmark result.

Validation:41focused tests passed; Ruff/mypy151passed. GitHub Actions45833469991 on20579ab
passed1,264SQLite tests and1,264PostgreSQL tests, actual-model smoke, dependency audit,
JS syntax and migration/seed/replay/downgrade. Each database run has one existing Starlette
warning. Detailed artifacts remain ignored and delivery stays disabled.
