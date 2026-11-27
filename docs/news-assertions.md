# Source assertions and graph applicability

The local candidate adds a shared assertion layer to [news-framework](news-framework.md).
Core policy9 retains the numerical editorial weights. No stock-price, financial
magnitude, verified actor, or notification decision is produced by this layer.

`news-assertions-v1.json` declares activity classes READINESS, PRODUCTION, CAPACITY,
CONSTRAINT, ADOPTION, FINANCING and AGREEMENT, negation, explicit planning/retrospective markers and
industry-scope terms. `news_assertions.frame` records original text and relative
spans, component/market vocabulary, activities and phase. Actor, recipient,
platform, reference period and financial impact remain UNKNOWN. A named-scope
match is retained separately as a candidate subject span, never a resolved identity.

Profiles may attach `assertion_scope` to a CLASSIFIED_CONTEXT or SCOPED_ACTIVITY
binding. It declares a mode, sourced subject terms, activity classes and a specific
incident SOURCE_BACKED relationship. All declared names must occur in binding
evidence; the graph must have a valid route through the specified relationship.
Read-time expiry, withdrawal and source integrity still apply. Optional fields
are omitted from legacy serialization; previous profile hashes are preserved.

| Mode | Required source evidence | Intended use |
|---|---|---|
| NAMED_OPERATOR | Explicit sourced name or bounded joint names with an active/planned predicate, or explicit passive by-agent; names must be sourced | Facility/operator-specific supply or named-competitor activity; mention as customer/comparison is insufficient |
| NAMED_PLATFORM_OR_MARKET_CONSTRAINT | Named platform in the assertion, or explicit industry breadth + component + data-center market + constraint | Named deployment narratives with a conditional industry-constraint route |

The matcher checks successive source windows until an eligible one is found, splitting contrast clauses.
No subject is donated from a title to a different sentence. RSS and complete-body
matching share this contract; path selection cannot silently choose a different
edge to bypass the scope. Trace/explanation preserves the qualifying bridge.
Constraint classification is COMPONENT_CONSTRAINT/INPUT_MARKET_CONTEXT, distinct
from product readiness. Existing source/context and priority gates remain separate;
adding an assertion does not automatically promote a background card.

Data migration materializes all four missing competitors named in one existing
competition paragraph, not a single peer selected from a failed headline. Each
receives its own node, sourced relation and scoped binding. Narrow supply and
platform bindings are migrated using the same schema. Detailed profiles stay local.

## Boundaries and next work

This is a conservative English pattern parser, not complete linguistic role
resolution. Irregular/complex passive predicates, unsupported joint-subject syntax, indirect speech, pronouns and
cross-sentence attribution may be withheld. Literal platform co-occurrence still
does not establish compatibility. Unmarked historical assertions can retain
SOURCE_REPORTED because the parser does not invent a date; phase and financial
effect must not be conflated. Source quote checks establish literal support,
not independent semantic verification of a relation.

Regression measurements use existing exposed AI references with unchanged targets.
They cannot establish unseen-market accuracy; losses on other cohorts must remain
visible. Before broader rollout, collect a predeclared fresh family-diverse cohort,
freeze candidate predictions and use independent reviewer contexts. Core product
acceptance is unchanged. Local data only, notifications disabled.

Candidate workspace: `source-cache/assertion-routing-workspace-2026-11-27.json`.
See the latest CHECKPOINT/QUALITY_REVIEW and aggregate assertion-routing-review report.

## Operator grammar revision (2026-11-27)

Assertion vocabulary version2 retains all predicate occurrences, so an earlier verb
from another actor cannot hide a later valid predicate of the same class. Bounded
active auxiliaries/adverbs support joint named subjects and explicit plans (`to`,
`plans to`, `will`). Regular passive predicates require an explicit `by` agent;
a passive patient, recipient, agentless passive or supplier-of phrase is insufficient.
Names come only from source-backed profile data. Traces retain exact subject and
predicate spans, voice and planned phase; identity and financial effect stay unknown.

For SCOPED_ACTIVITY with this contract, the accepted typed predicate supplies the
action test. The legacy change-term vocabulary no longer applies a second competing
action test. Topic, product/facility context, exclusions, evidence validity and the
declared graph edge still apply. Tests use interchangeable fictional names.

The local SNDK12 migration connects existing sourced memory/solid-state-drive and
Yokkaichi/Kitakami facility scope to the same binding. SSD/SSDs are explicitly traced
aliases of solid-state drives, not invented quotations or new financial evidence.
No company-specific code branch, changed narrative target or numerical weight.

Current opt-in manifest: `source-cache/actor-resolution-workspace-2026-11-27.json`.
The preceding assertion-routing workspace remains intact. Blind evaluation locks
both candidate predictions and predictions executed by an archived previous runtime
before reviewers start; running old profiles through new code is not that baseline.
