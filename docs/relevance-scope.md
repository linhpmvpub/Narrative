# Source-bound relevance scope

The local candidate now separates three kinds of informational relevance. This
extends the compact company profile; it does not add a price forecast or enable push.

| Role | Database requirement | Meaning on a news card |
| --- | --- | --- |
| OWN_PRODUCT | Same-sentence company subject, scoped topic/action, source evidence; subject must identify the profile company | News names the company in the applicable market; an order or impact is not verified |
| SHARED_MARKET | Reviewed factor/path and same-sentence market/activity; sourced exclusions for known competing subjects | Market context, with customer and hardware participation unknown |
| COMPETITOR_PLATFORM | Named subject with evidence, product anchor, outgoing sourced COMPETES_WITH relation present in the selected route | Competitive product context; substitution, share and profit effects unknown |

`FactorBinding.relevance_scope` is optional and omitted when absent, preserving
legacy serialized profile hashes. Scoped rules reject aliases and unsupported
subject names. Each rule retains the existing source, review, expiry, narrative
and graph contracts. Runtime path selection must include the declared competition
edge; an alternate route cannot bypass an expired edge. Revoked relationship or
profile evidence withholds the candidate.

For full articles, the title can **exclude** a competing issuer's broad market
context, but cannot supply a missing positive subject or term to another sentence.
This rule is shared by source-card projection and evaluation. It is a conservative
scope guard, not complete article-level entity or coreference resolution.

Shared-market and competitor spans are explicitly context-only. Direction words
in those spans do not earn concrete-change editorial points. A separate supported
direct/activity path can still justify a priority card. Core policy version4 keeps
the existing numerical weights. The core UI labels these roles inside the source
path explanation; financial direction, magnitude and lag remain unknown.

## Sourced local database

The candidate adds one AMD accelerated-computing product node and one competition
edge in NVIDIA's profile, using the [NVIDIA fiscal2026 annual filing](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm).
The original capture, exact quote and review timestamps remain local. This is a
scoped issuer disclosure of competition, not evidence that any individual news
event caused a lost NVIDIA order. The named scope deliberately does not turn an
acquisition integration announcement or research funding into a competing product
release. Google/Alphabet alias resolution is not asserted by this new node.

The new snapshot has6profiles,77nodes,84relations,7sources,39exposure facts,
13financial sets,4financial bindings and8entity references. Source cells were
reverified and the input-market registry repinned. No numerical economic exposure
was invented. Use `source-cache/context-scope-workspace-2026-11-26.json`, which
points to `context-scope-2026-11-26/profiles-v2`, `atlas-v2` and `registry-v2`.
Earlier candidate versions, source captures and frozen predictions are preserved.

## Measured tradeoffs

See [aggregate results](../reports/relevance-scope-regression.json). The comparison
is against the preceding activity-routing candidate, using exposed two-agent AI
labels and unchanged narrative targets. It is not a new blind evaluation or human
gold. Cohorts are reported separately; do not pool overlapping economic stories.

| Track | Pairs | True positives before → after | False positives before → after |
| --- | ---: | ---: | ---: |
| Older RSS | 1716 | 45 → 54 | 4 → 4 |
| Archived disclosure excerpts | 300 | 5 → 5 | 0 → 0 |
| Older complete articles | 150 | 22 → 22 | 1 → 2 |
| Recent RSS | 216 | 5 → 5 | 0 → 0 |
| Recent complete articles | 30 | 2 → 2 | 0 → 0 |

Older RSS selected unresolved pairs rise11→12. Full-article selected unresolved
pairs rise0→1; its extra false positive is background context, not a priority card.
Older RSS priority selection finds17/96resolved relevant pairs versus16previously,
with2false positives. Informational recall56.3% and editorial selection remain
insufficient for v1 acceptance. The scope labels themselves have not received a
fresh independent semantic review. The candidate remains local and opt-in.

## Next priority

The main remaining distinction is between components/application software and
actual infrastructure demand. Add explicit market/product applicability in the
database, with sourced counterpart aliases and competitive mechanisms where
supported. Preserve useful background even when priority is unproven. Test these
groups and near-misses together, retain ambiguous labels, then lock a new unseen
cohort with meaningful MU/SNDK support. Do not replace group-level rules with a
list of title exceptions or lower acceptance targets to claim completion.
