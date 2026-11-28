# Company intelligence foundation and optional narrative product

## Implementation status — 2026-11-28

Foundation step1 is implemented: company schema, matching, assessment, ranking, primary API/feed
and UI do not require narratives;120real-case removal invariance verified. Step2 now has the reviewed
body lifecycle bridge; broad company event/evidence coverage remains incomplete. Step3 has a frozen
direct-company relevance/attention benchmark and combined freshness gate; explanation/human/operations
dimensions remain open. First6.50/100 exposes major coverage gaps; no comparable change from25.18legacy.
See [implementation](company-assessment.md), [benchmark](company-benchmark.md) and [review](../reports/company-foundation-review.md).
Next implement reusable company event/exposure coverage and fuller sources before watchlists/history
and optional narratives. Remaining target text below describes the full roadmap, not completed v1.


User direction, 2026-11-28. This document specifies the target and next work, not
implemented capabilities. It supersedes narrative-first sequencing and treating
example narratives as the coverage boundary. Existing sources, tests and frozen
evaluation references remain valid within their original scopes.

## 1. Primary product: company news intelligence

The product answers: what happened, which companies may be affected, through what
business relationship, how much attention the development warrants, and what is
known or missing? It must work with zero user narratives and zero example templates.

The primary path is:

`collection → source revisions/deduplication → substantive assertions/events →
entity/product/market resolution → sourced company exposure → company assessment
→ explanation/card/company timeline → user watchlist and attention policy`

The relationship database owns issuer identity, products/segments, inputs,
suppliers/customers, markets, competitive roles, geography/assets and financial
exposure. Common mechanisms and explicit scope/conditions connect events to those
facts. Preserve the bounded seven-group v1 framework; populate core data before
expanding breadth. Examples exercise contracts; names/headlines never become code
exceptions. An article need not name an issuer when a sourced exposure supports it.

Each proposed company assessment contains:

| Field | Meaning and evidence boundary |
|---|---|
| Source development | Exact assertion, source/version, event family, actor/asset, period and lifecycle |
| Company relevance | Direct issuer or indirect scoped exposure, applicable product/segment and evidence path |
| Mechanism | Conditional channel, affected business variable, conditions and mitigating factors |
| Attention priority | Novelty, substantive change, exposure, potential importance and evidence quality; separate from impact size |
| Direction | Direction on a specified business variable, possibly mixed/unknown; not an automatic stock-price forecast |
| Magnitude | Source-supported quantity or explicitly labelled scenario/prior; unknown without scope/denominator |
| Horizon | Supported transmission window and its basis; article age is not impact horizon |
| Confidence and gaps | Strength/conflicts of evidence, unverified assumptions and missing facts; not a made-up probability |
| Explanation/history | Concise reason to read, source links, changes since the previous revision and supersession |

Unknown financial magnitude does not block useful company context. Conversely, a
graph route does not prove a realized customer order, causal effect or material
financial change. Do not promote generic background into an alert merely to expand
coverage. Reuse existing typed actor/asset/mechanism and source lifecycle guards.

## 2. Advanced product: user-defined narrative tracking

Narratives consume company assessments and the common event/relationship database;
they do not control what the foundation collects or recognizes. Shared market or
policy events can remain available even before an issuer mapping is established.
Existing seed narratives are examples/regression fixtures, not a closed product
catalog. A user may describe a new thesis beyond those templates. Unsupported or
ambiguous scope must remain explicit, rather than promising universal coverage.

A future narrative specification should preserve:

- Original user wording, author, creation time and immutable initial version.
- Companies/markets, variables, causal propositions, assumptions and intended horizon.
- Observable milestones/outcomes, starting baseline and comparison period.
- Conditions that support, weaken or invalidate the thesis, declared before assessment.
- Separate revisions when the user changes a thesis, horizon or success criterion.

The interface helps turn free text into a reviewable specification. It must not
silently substitute a different claim or an easier success criterion. This is a
future product flow, not a requirement to ask the project owner to approve routine
implementation work.

## 3. Timeline and retrospective thesis evaluation

Maintain an append-only evidence history: source event/quote, relation and profile
versions, system assessment, narrative version and why the evidence supports,
challenges or leaves the thesis unresolved. Corrections/retractions supersede prior
records; they do not erase what users and the system previously saw.

Distinguish event time, publisher time, first available/captured time, assessment
time and subsequent revision time. A historical replay may only use evidence and
database versions available at its cutoff. Current-profile retrospective analysis
must be labelled separately and cannot establish prospective prediction accuracy.

The visualization should show the original thesis, dated developments, milestones,
supporting AND contradictory evidence, changes in assessment, and final observations.
Keep two questions separate:

1. **Evidence progress:** what developments currently support/challenge each part?
2. **Outcome assessment:** did the predeclared observation happen within its window,
   with the specified baseline, magnitude/direction and scope?

Use states such as supported, contradicted, mixed, not yet due and insufficient
evidence. A numeric error/score requires a measurable, predeclared target and actual
outcome. Counting supportive headlines is not prediction accuracy. Do not fabricate
a percent-correct score for a vague thesis. Track timing and magnitude separately;
business-thesis validity, mechanism validity and share-price performance are distinct.

## 4. Implementation order and acceptance work

1. **Remove foundation dependency on narratives.** Audit matching, ranking, API,
   UI and evaluation. Company discovery already exists, but current priority and
   much of the main feed still use narrative projections. Make company assessment
   and its primary card usable without templates; retain optional narrative links.
   Acceptance tests must show that adding/removing a narrative cannot change the
   same input's company relevance or company priority. Preserve prior regression
   targets and document deliberate output migrations.
2. **Improve company evidence and assessment.** Bridge reviewed substantive article
   content, versioned sources and general company scopes. Cover results, inputs,
   supply/capacity, customer demand, financing/access and competitive developments.
   Separate primary developments from incidental prose; explain unknown magnitude
   and horizon. Keep sourced database completion focused on reusable failure classes.
3. **Evaluate the company product directly.** Freeze a new company-level benchmark
   policy/target/sample/predictions before independent labels; assess discovery,
   company attention priority and explanation fidelity independently of narrative
   targets. Report false matches, misses, unresolved evidence, group/company support
   and operational coverage. Retain the old mixed score as a labelled legacy series;
   no retroactive reweighting or comparison across score definitions. Numerical
   release gates remain unmet until checked against the correct versioned target.
4. **Company experience and reliability.** Watchlists, deduplication, useful summaries,
   evidence diagrams and source/event/company histories; attention budgets and
   corrections, then operational/user acceptance. No automatic cloud or push activation.
5. **Narrative extension.** Build free-text thesis specification, user-confirmed
   interpretation, evidence tracking, timeline replay and outcome assessment on the
   stable company foundation. Preserve temporal/version fields now; defer richer
   narrative UI/scoring instead of optimizing the example catalog first.

Changing the product target requires explicit new benchmark/acceptance versions,
not reassignment of old labels. The current 25.18/100 mixed index is not a validated
company-product score. Documentation updates alone do not improve that result.

Private data stays local. SEND_NOTIFICATIONS=false, ALLOW_SYNTHETIC_LIVE=false and
LLM_MODE=none remain in force. This direction does not authorize hosting, live push,
paid services or new runtime LLM calls.
