# Diverse-event blind pilot

This pilot evaluates the frozen reading-card matcher against complete public articles
using the existing current company profiles. It does not change routing rules or weights.
Private source captures, selections, predictions, traces and independent labels stay in
ignored `source-cache/diverse-events-2026-11-24/`. No live feed or notification setting changes.

## Protocol and coverage

The collection protocol was recorded before predictions. The database/runtime baseline
pin is `d5dcf77abc4b6ccf07a0d05274190f0c35d6825c95b994b6c58b6f41b871416b`.
Each evaluated profile hash matches the frozen atlas. Article predictions were locked
at 2026-11-24T13:12:45.351360Z, before independent review, using `feed_cards`.

There are 23 retained document clusters and 230 article/narrative pairs across five
companies, six profiles and ten narratives. Dates range from April 2024 to August 2026.
The seven primary sampling families contain:

| Family | Articles | Included controls |
| --- | ---: | ---: |
| Supply disruption / weather | 2 | 0 |
| Input prices | 3 | 0 |
| Capacity / facility investment | 2 | 0 |
| Demand / customer adoption / results | 6 | 0 |
| Technology | 4 | 1 award announcement |
| Financing | 3 | 1 third-party mini-tender |
| Policy | 3 | 1 government-relations appointment |

Controls belong to a sampling bucket, not to a verified economic mechanism. Broad
market articles can also be irrelevant to a particular narrative; reviewers decide.
Sources include SEC issuer statements, EIA, Federal Reserve, NVIDIA, AMD, Dell,
SK hynix and Sandisk. Three Micron article URLs returned 403; this cohort therefore
has no direct Micron issuer article. It still evaluates both MU narratives on every
article. The initial aspiration of 28-35 articles was not met; coverage gaps remain.

URL and text-shingle exclusion checked 30 prior packet files (23 distinct packet
hashes, 432 observed URLs). Candidate titles and projects were also inspected;
a multi-customer roundup was omitted to avoid overlapping the chosen deployment.
No retained URL/text duplicate was rejected at final freeze. These checks do not
prove independent economic shocks: market reports, suppliers and customers can
share underlying themes. Report article counts separately from correlated pair counts.

Body boundaries were reviewed before capture/freeze, retaining qualifications and
financial appendices while excluding site navigation and generated summaries. Cached
publication dates are source assertions; current capture is not evidence of historical
availability or an unrevised original article. Day-only dates use end-of-day UTC.

## Blind review and interpretation

Two AI agents receive identical source/profile/narrative evidence in separate contexts,
without matcher rules, predictions, traces or peer labels. Every pair requires a label
and rationale. Labels are RELEVANT, NOT_RELEVANT or INSUFFICIENT_CONTEXT.
Disagreements remain unresolved; they are never converted into negative labels.
Relevance means useful sourced information for the particular narrative, including
credible industry or partner context, without assuming realized financial impact.

These are independent AI judgments, not human gold, and context separation is not
filesystem isolation. Precision/recall exclude unresolved references and must include
the unresolved count and selected-unresolved count. Report per-family and per-company
results rather than only one pooled number. No tuning on this cohort.

This test covers reading relevance only. It does not validate causal applicability,
transmission channel, magnitude, direction, duration or push suitability. Current
atlas scenarios need explicit operator event/factor input and retain unknown strength;
manual event framing must not be scored as automatic extraction. Financial segment
shares remain reporting facts, not impact weights. A separate group-labelled causal
benchmark and historically valid profile snapshots are still required.

## Local reproduction

Keep the baseline and private workroot intact. Set `DEV_INFORMATIONAL_FEED=true`,
`COMPANY_PROFILE_ROOT=source-cache/financial-context-2026-11-24/profiles`, and
`NEWS_ARTICLE_DIR=source-cache/diverse-events-2026-11-24/articles` for evaluation.
Verify the baseline with `engine.atlas_freeze verify` and its recorded pin. The existing
`engine.evaluation.article_relevance` freeze and `engine.evaluation.profile_relevance`
consensus/evaluate commands retain source integrity and label coverage checks.
Never recreate or overwrite this frozen cohort to improve its results. Aggregate
results may be committed; full bodies, URLs, per-pair labels and predictions stay local.
