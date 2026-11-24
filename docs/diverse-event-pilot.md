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
has no direct Micron issuer article. It still evaluates the frozen MU narrative on every
article. The ten frozen narratives include one MU narrative and three NVDA narratives
(including a historical H20 example); this is not an evenly balanced two-per-company set. The initial aspiration of 28-35 articles was not met; coverage gaps remain.

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

## Acceptance gaps

The existing group criteria require at least 20 independent economic-event clusters,
10 resolved positive clusters and 10 resolved negative clusters per group. This pilot
has only 2-6 documents per sampling group and cannot pass those gates. Source-phase,
horizon-support and strength-support AI annotations were prepared separately after the relevance freeze;
they are not predictions and cannot establish end-to-end impact accuracy. Entity,
exposure-scope and mechanism applicability still need pair-level independent review.

## Pilot results (AI consensus)

Of 230 pairs, 205 have resolved references: 11 true positives, 1 false positive,
142 true negatives and 51 false negatives. There are 25 unresolved pairs, including
13 reviewer disagreements; one unresolved pair was selected by the matcher.
Precision is 11/12 (91.7%); recall is 11/62 (17.7%). These denominators exclude
unresolved references, and the small number of selected examples makes precision
especially uncertain. This is not a market-wide accuracy estimate.

| Group | Correct relevant / reference relevant | Recall | Unresolved pairs |
| --- | ---: | ---: | ---: |
| Supply disruption | 0 / 6 | 0% | 3 |
| Input prices | 0 / 12 | 0% | 6 |
| Capacity | 4 / 12 | 33.3% | 0 |
| Demand | 3 / 15 | 20% | 9 |
| Technology | 0 / 6 | 0% | 0 |
| Financing | 2 / 6 | 33.3% | 2 |
| Policy | 2 / 5 | 40% | 5 |

The technology group contains the one resolved false positive. All three designated
controls were rejected for all ten narratives. By company, resolved positive retrieval
was AMD 0/11, DELL 5/16, MU 0/8, NVDA 6/25 and SNDK 0/2. These are correlated
pair counts, not independent company-level accuracy trials.

Diagnostic review found a lexical scope failure: an embedded RF-chip description
using figurative building-on-prior-success language was routed to server adoption.
Missed groups include named foundry disruption, energy-market context, memory
competitor production and issuer storage results. Reading relevance does not imply
a verified company financial effect. No individual rule or weight was changed.
Code inspection confirms that reading-card retrieval still begins with reviewed
`factor_bindings` and sentence-level text matches, then checks graph paths. New
atlas exposure facts and financial reporting layers do not automatically add event
recognition. Database breadth alone therefore does not imply news-retrieval coverage.
The next general capability is typed event-to-factor grounding with product/entity
scope, followed by graph routing; adding article-specific synonyms would not close
this architectural gap.
The evaluated matcher does not apply news freshness eligibility to these predictions;
low retrieval is not simply the consequence of old publication dates being filtered out.

Both reviewers also supplied 23 source-level phase/horizon/strength-support labels.
Agreement was 15/23 on phase, 20/23 on horizon support and 23/23 on strength support.
This is agreement, not accuracy. Mixed-phase articles still need adjudication. A
quantified source-issuer effect may concern a supplier outside the five tracked firms;
it cannot be transferred to their revenue or margins. Reviewer horizon text may be
paraphrased and is not a validated quote. Full pair-level causal labels remain pending.

## Next implementation priorities

1. Freeze the exposed pilot as a diagnostic set. Keep all source captures, both reviews,
   predictions and disagreement records; never relabel it as a fresh holdout.
2. Extend structured source-backed factor coverage by mechanism: foundry/facility
   interruption, regional energy conditions, memory technology/capacity and customer
   deployment. Keep industry context distinct from a verified supplier/customer edge.
3. Add general event-action and product-scope interpretation, separating an actual
   build/order/production change from rhetorical wording, research or an award.
   Preserve proposed/committed/operating distinctions and explicit unknown exposure.
4. Adjudicate the phase rubric, label entity/scope/channel/horizon/strength separately,
   and collect new economic clusters to reach the existing per-group quotas. Restore
   direct Micron coverage and expand Sandisk positive and negative examples.
5. Compare a deliberately versioned successor engine on a new blind grouped holdout.
   Calibrate relationship weights only after supported exposure and independent
   causal-group labels; leave notifications off until product acceptance passes.

## Validation and storage

CI run 45401712334 on protocol commit fea7da9d28115e4391c1f71b5600c5edb441127f
passed 944 SQLite tests (139.78s) and 944 PostgreSQL tests (254.19s), dependency
audits, Ruff, mypy (130 files), JavaScript syntax and migration/seed/replay/downgrade.
Frozen source/label integrity and aggregate reconciliation were rechecked locally.
The final handoff changes documentation and sanitized aggregate results only;
engine/config/profile fingerprints stay unchanged. Raw evidence and reviews remain
local; real notifications, synthetic live delivery and cloud data deployment stay off.

A redundant Windows full-suite run was intentionally stopped after 91% progress
once both complete CI suites had passed; it is not reported as a local full-suite pass.
