# Company assessment and private feed

## Issuer-event extension — 2026-11-28

[Shared issuer contracts](issuer-events.md) add financial-performance, shipment and capacity
recognition with exact actor/action/object and source-window traces. Attention uses the unchanged
event sentence and preserves explicit forward plans; cards state completion is unconfirmed.
Company score is now10.64on the same fixed reference (+4.14); older6.50figures below describe
initial foundation acceptance. Sources/graph/numeric financial data remain unchanged; no impact
magnitude or generalization claim follows from this small exposed-reference gain.


Implemented 2026-11-28; this is the company foundation, not completed v1 acceptance.
Follow [product direction](../codex/PRODUCT_DIRECTION.md), [workflow](../codex/DEVELOPMENT_WORKFLOW.md),
[principles](../codex/PRINCIPLES_AND_LESSONS.md) and [company-first plan](company-first-product-plan.md).

## Runtime contract

`RSS revisions / reviewed complete body → source-local statements → company discovery
→ sourced exposure and company-membership path → company assessment → primary card`

`company_discovery.source_decisions` is shared by RSS, reviewed articles and direct-company
benchmark. `company_assessment.assess` is shared by the benchmark and `company_feed`.
Neither requires a narrative or calls narrative projection. Existing narrative APIs and
mixed-target regressions retain their own semantics. `/api/v0/news/core` now uses the
company feed as its primary context; existing authentication and local-source checks remain.

A discovery needs an explicit issuer event or exact sourced factor and company-membership
paths. A company mention, generic theme or competitor/customer link is not ownership.
Names, product scopes and relationships belong to profile data, not ticker branches.
Every supported binding kind may be company-only when an explicit discovery rule references
it and narrative_ids is empty. Its source, typed mechanism and timing checks still apply.

Company assessment exposes relevance, attention tier, source statements/spans, conditional
business channels, unknown direction/financial magnitude/horizon, policy hash and version
trace. Financial context and exposure parameters retain their source/period; they do not
become an estimated event effect. Profiles without company discovery are reported as gaps.

## Attention, not impact magnitude

`config/company-assessment-v1.json` declares ordinal tiers:

| Tier | Attention | Basis |
| --- | --- | --- |
| ISSUER_DEVELOPMENT | Main feed | Explicit eligible issuer development |
| EXPOSURE_DEVELOPMENT | Main feed | Scoped concrete development through sourced exposure |
| RELATED_BACKGROUND | Background | Relevant context without qualifying development |
| SPONSORED_CONTEXT | Background | Sponsored/advertorial title |

The numbers order tiers only; they are not fitted impact weights, financial probabilities
or a claim that all issuer events matter more economically than indirect developments.
Shared source-activity exclusion/scope helpers remain conservative. Future calibration
must distinguish discovery misses from attention mistakes before adjusting weights.

## Reviewed full-body lifecycle

Workspace manifests may set reviewed_articles to a local ARTICLE_FEED_V1 directory.
The profile registry must be the same as the workspace registry. `article_feed.current_selections`
verifies review boundaries, packet and visible-text hashes, current RSS anchors, enabled
sources, withdrawal status and a source check no older than one hour. Corrections are held
for review; refresh cannot revive REVIEW_REQUIRED or WITHDRAWN entries.

All registered full-body URLs suppress RSS fallback, including held/stale bodies. This
prevents an old RSS excerpt from silently restoring a corrected article. Eligible bodies
produce source-linked company cards, deduplicated against RSS, subject to the same publication
age and company rules. Projection rechecks registry/source-state consistency. A full-body
label means that representation was checked, not that every match comes from its body or
that the publisher's financial claims are independently confirmed.

The current local acceptance snapshot contains 70 attention and 47 background cards, including
one reviewed issuer release replacing its RSS representation. Its retained issuer match is
in the title; body-only recovery is covered by a synthetic integration case, not claimed as
an independently measured real-news gain. Eight source bodies pass current source checks;
eight remain held. Seven older eligible source bodies yield no current company card. Source
check eligibility and company/publication-age eligibility are separate.

## Verification and remaining work

Tests cover zero-narrative operation, invariant IDs/assessment/evidence, source correction,
withdrawal, expiry, version/pin mismatch, source proof and sponsorship/uncertainty. A local
metamorphic replay removes all narratives from five real profiles: all 120 source-company
results remain exactly identical. Desktop/mobile rendering uses actual assets and a local
routed snapshot; it does not establish deployed service or remote access.

Current extraction has narrow English event predicates and incomplete company/event scopes.
See [direct-company benchmark](company-benchmark.md): the initial 6.50/100 result shows severe
missed coverage. Next improve reusable company event contracts and sourced product/market
exposures, source completeness and typed roles. Watchlists, summary fidelity, company histories,
attention budgets and operational/human acceptance remain open. Narrative thesis history and
outcome scoring follow the company foundation. Data local; delivery/cloud/runtime LLM disabled.
