# Independent relevance and priority evaluation — 2026-11-26

This iteration tests the previously locked broader-context candidate against separate
informational-relevance and editorial-priority references. Two independent AI contexts
reviewed source-only packets, with no prediction or peer-label access declared. These
are AI judgments, not human gold or independent factual verification. No notification,
deployment or weight change follows automatically from this experiment.

## Collection and unseen-content boundaries

Added public AMD and Sandisk investor-relations RSS feeds to the source configuration,
with30-minute poll intervals. An isolated local SQLite copy collected10records from each.
Existing feeds added4records and revised2; all10attempted sources completed OK/NOT_MODIFIED.
Raw captures and revisions remain local. No running service or tunnel was reconfigured.

- AMD: https://ir.amd.com/news-events/press-releases/rss
- Sandisk: https://investor.sandisk.com/rss/news-releases.xml
- Micron's legacy public RSS and investor landing page returned403. Neither authentication
  bypass nor repeated retries were attempted; Micron issuer coverage remains incomplete.

The sampler now accepts an explicit profile root, a bounded5000row scan, source quotas,
and a predeclared title-exclusion pattern. Historical text relevance permits up to365days;
live-feed evaluation retains its30day ceiling and all actual feed freshness rules remain
unchanged. The current study used180days, not a claim that six-month-old news is live.

Twenty-five unique prior packet hashes were excluded, including previously exposed core
context cards and prior unlabeled frozen packets. The RSS freeze rejected302previous
exposures,9earnings/report titles and5conflicting/invalid clusters. Financial-result items
were conservatively excluded rather than assuming that a new URL means an unused period.
Source quotas requested8AMD/8Sandisk records, but after exclusions yielded0AMD/1Sandisk.
**The issuer enrichment target was not met.** Remaining slots use declared topic sampling;
the actual source composition and shortfall must accompany the sample count.

The resulting24RSS articles/216narrative pairs are a new unseen-content challenge with
current profiles, not a prospective market sample. Two reviewers flagged one possible
overlap between tariff stories;24lexical clusters must not be called24verified independent
economic events. No false precision from cluster counts is claimed.

A separate bounded public AMD archive page yielded three unused complete releases:
an acquisition agreement, a technical appointment and a UK investment/infrastructure plan.
The original HTML/text was captured and hashed; inspected body boundaries include the
complete release through cautions/contacts and exclude menus/footers. Exact publication
timestamps were converted from EDT to UTC. Existing source-body verification and substantive
block extraction suppress About/caution boilerplate and prevent cross-sentence matching.
This cohort has30pairs/3clusters and is not pooled with RSS or represented as historical
as-of evidence. No additional unseen Sandisk positives were manufactured from reused pages.

## Labels, predictions and integrity

`engine.evaluation.priority_review` freezes baseline and broader selections, profile/runtime
hashes and a compact prediction-free packet before reviews. It reuses strict two-reviewer
identity/time/coverage/declaration checks and source-body verification. The packet includes
company relationships, narrative scopes and source references; matching rules are omitted.

Relevance: RELEVANT, NOT_RELEVANT, INSUFFICIENT_CONTEXT.
Priority: PRIORITY, CONTEXT, NONE, INSUFFICIENT_CONTEXT. Priority requires a specific scoped
development; concrete plans may qualify as plans, without claiming completion or profit
effects. Routine/educational context is assessed separately. Negative relevance requires
NONE; unresolved relevance cannot silently become a resolved priority judgment.

Reviewers also label actual event groups independently from lexical sampling strata.
Financial-services adoption is not a financing event. Groups must be consistent across
the article's company/narrative pairs. The initial RSS rubric omitted the enum listing;
both reviewers received the same pre-existing allowed taxonomy before completing labels.
The archive packet includes it explicitly. Frozen files were not rewritten.

Disagreements remain unresolved per dimension. The implementation agent does not cast a
deciding vote. Priority and relevance are scored separately, with selected-unresolved and
positive-cluster counts. Duplicate flags remain visible, not silently discarded.

## Observed results

| Cohort/variant | Relevance TP/FP/FN | Unresolved | Priority TP/FP/FN |
|---|---:|---:|---:|
| RSS baseline |0/0/7|56/216|0/0/5|
| RSS broader context |0/0/7|56/216|0/0/5|
| Complete-body baseline |1/1/1|3/30|1/1/1|
| Complete-body broader context |1/2/1|3/30|1/2/1|

RSS:33relevance disagreements and33priority disagreements;3articles have unresolved event
groups. The engine selects no pairs, so precision is **undefined**, not100%. Recall is0/7;
five resolved relevance clusters and four priority clusters provide little positive support.
Unresolved fraction25.9%exceeds the20%target. The broader threshold cannot recover news that
never passed factor matching. Two relevant pairs are sponsored context, correctly not
interpreted as a recommendation to promote sponsored material into priority alerts.

Archive: both reviewers agree on all labels. Broader selection finds the same1TP as baseline
but adds a second FP and selects one unresolved pair. Baseline precision1/2vs broader1/3;
recall1/2in both. Only two positive references exist: one AMD and one DELL. These counts do
not establish general accuracy. MU/SNDK still have no resolved positives in either cohort.

The candidate is rejected for promotion. Neither this sample nor the earlier exposed
calibration justifies changing40/30/20/20weights, main-card visibility or commodity thresholds.
Financial magnitude, lag and notification utility remain uncalibrated.

## Review and next implementation priority

The failure is upstream of weighting. RSS misses include actual facility-development,
investment-partner and GPU-deployment statements; narrow term conjunctions fail to connect
them to existing infrastructure-demand factors. Archive errors include treating AMD-specific
acquisition/infrastructure developments as NVIDIA customer buildout, while missing the
explicit AMD roadmap connection. Reviewer interpretations do not establish an actual DELL
order or NVIDIA hardware identity; those remain unknown.

Next implement reusable event-role/scope handling: distinguish project/operator, funder,
product/vendor, action and event phase; attach a source-grounded facility/compute-development
event to applicable profile factors; stop vendor-exclusive developments from becoming
another company's customer-demand claim unless an explicit shared mechanism applies.
Use these now-exposed failures and the existing calibration corpus as regression, never
claim a new blind improvement on the same labels. Then lock another candidate and acquire
a new independent cohort. Keep competitor effects separate from customer deployment.

Continue sourcing unseen MU/SNDK positives and fuller bodies where excerpts are insufficient.
Public source availability and positive-reference coverage remain blockers to acceptance,
not reasons to invent labels, reuse excluded periods or loosen source/identity checks.

## Local artifacts and validation

Detailed captures, plans, frozen predictions and both reviewer outputs are under ignored
`source-cache/priority-blind-2026-11-26` and `source-cache/priority-issuer-archive-2026-11-26`.
The aggregate report is `reports/dual-priority-evaluation.json`. Calls are local Python APIs:
`profile_relevance.freeze`, `priority_review.freeze`, `priority_review.evaluate`; use a new
directory for every freeze and preserve receipts. Full-body evaluation requires its original
`NEWS_ARTICLE_DIR`. No raw articles, per-case labels or databases are committed.

Focused validation:45tests passed,1existing Starlette warning; Ruff and mypy152passed.
Full CI is recorded in the checkpoint after completion. Live notifications remain disabled.
