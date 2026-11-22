# Historical archive reconstruction v1 — 2026-11-22

Completed60 real issuer-period clusters,180 source passages and540 blind AI
passage reviews. SEC captures, predictions, labels and individual comparisons
remain local under ignored `source-cache/historical-replay-v1/`. No graph/event
promotion, notification, production-data migration or source upload.

Freeze anchor9366c586c182bd1ec40eb5069811ac8453396495 was pushed before independent
review began. The packet/prediction/source collection hashes are in
`historical-replay-freeze.json`. Evaluation workflow code312387c did not change
the frozen classifier, cases or predictions. Aggregate machine-readable result:
`historical-replay-summary.json`; source/label provenance is represented by hashes.

## Corpus and review

Publication dates2022-01-06 through2025-12-18. MU17,AMD16,NVDA15,DELL8,SNDK4.
These are quarterly/annual information clusters, not180 independent events.
Each cluster supplies three deterministically sampled financial/change/risk or
description passages. Retrieval occurred in2026 and was not backdated. Historical
archive reconstruction is separate from the unchanged strict production replay.

All three fresh-context AI personas completed60 clusters/180 passages each,
without predictions or peer votes. All verified60 raw source hashes and180
canonical-JSON passage hashes. The financial expert then adjudicated26 disputed
passages, retaining the original blind review.154 passages were unanimous,
25 disputes resolved,1 deferred. No human labels were produced.

## Language agreement with AI reference

| Partition | Clusters | Available passages | Resolved | Matches | Agreement | Cluster bootstrap95% |
|---|---:|---:|---:|---:|---:|---:|
| Development2022–2023 |25|75|75|61|81.3%|73.3–89.3%|
| Calibration2024 |16|48|48|41|85.4%|75.0–93.8%|
| Temporal holdout2025 |19|57|56|41|73.2%|60.7–85.7%|
| Holdout subset excluding exact cross-split reuse/known H20 exposure |13|39|39|28|71.8%|56.4–84.6%|

The subset rule was frozen before reviews. Excluded cases remain visible in the
full holdout denominator. One deferred passage is not silently counted correct.
Intervals resample issuer-period clusters2000 times; they do not remove common
issuer/model bias, label uncertainty or LLM pretraining contamination. These are
AI-reference agreement figures, not independently validated accuracy.

A separately recorded post-hoc overlap audit compared all180passages with132
language texts from the prior204-case pilot using word-trigram Jaccard>=0.8:
0matches. This did not change the frozen scores and is not proof of no exposure,
semantic similarity or LLM training-data contamination.

## Findings and prioritized next work

Across179 resolved passages, references contain123 no-causal-claim,38 issuer
attributions and18 substantive financial outlooks/dependencies. Impact direction
is UNKNOWN130,NEGATIVE24,MIXED12,POSITIVE13.17 passages have AI-reference support
for a quantified financial effect. Those17 are review leads, not validated
normalized operands or approved graph edges; they still require period, identity,
unit, accounting scope and source-context checks.

1. **Separate disclaimers/descriptions from actual claims.**16/123 no-causal
   references were overcalled:12 outlook and4 issuer attribution. Sample errors
   include forward-looking-word lists and market/product descriptions. Scope
   guards should address these on development data, with a new untouched test set.
2. **Recover realized financial explanations.**11/38 issuer attributions were
   missed:10 called no-claim,1 called outlook. Reviewed cases include operating
   utilization charges and corrections to previously issued statements. Add
   evidence-aware parsing rather than broadening isolated cause keywords.
3. **Handle outlook and mixed temporal scope.**9/18 outlook references were
   missed:8 no-claim,1 issuer attribution. Financial consequences may span clauses;
   neither an isolated future verb nor a past-tense verb settles the passage.
4. **Expand representative event coverage.**Current sample is financial filings
   and biased toward descriptions. Add product/customer/regulatory announcements,
   corrections/reprints, material negatives and verified one/two-hop relationships.
   Near-duplicate boilerplate needs a preregistered grouping rule for the next run.
5. **Review accounting scope before mapping.**Post-spin SNDK filings may include
   predecessor/comparative periods. A filing published after separation does not
   make every historical operand standalone SNDK. Keep source/report periods and
   corporate identity explicit; do not treat a paragraph label as normalized impact.

## Release interpretation

The workflow is complete for this historical language/evidence benchmark.
The product is not cleared for live push. Push precision, two-hop recall,
material-event recall, price prediction accuracy and weekly false-alert rate are
unmeasured (`null`). No point-in-time verified graph was available for this corpus;
manufacturing one retrospectively would invalidate a historical graph test.

Next development batch should use the development partition for fixes, add
source-backed quantified cases and temporal relationships, then preregister a
new untouched test corpus. The2025 labels have now been inspected and cannot be
reused as a fresh hidden test for a tuned classifier. Keep prospective collection
and frozen protocol running as a separate validation track; no daily-data wait
is required to continue product development.

Planning estimate for5 tickers and the existing source scope:2–4 working weeks
for a private usable map/feed prototype;6–10 weeks for a controlled push pilot,
conditional on evidence coverage, agreed quality gates and operational/security
checks. Broader market coverage is a separate project estimate. These durations
are engineering estimates, not extrapolated from the73.2% agreement figure.
