# Editorial priority for scoped developments

The engine answers two separate questions: is this news related to a narrative,
and does the supplied source describe a concrete development worth highlighting?
Neither answer establishes financial impact or authorizes a notification.

`config/editorial-priority-v1.json` is the versioned contract. Actor names, products,
relations and narrative intent remain source-backed profile data; there are no
ticker, publisher or headline exceptions. Core policy13 retains numeric40/30/20/20
weights but changes eligibility and the resolved-entity feature: a named relationship
alone no longer receives an event's priority or score bonus.

| Input | Editorial requirement |
|---|---|
| Source assertion | Accepted actor/predicate/object scope and exact source-window offsets |
| Narrative route | Accepted sourced route; competition requires COMPETITION, input context requires SUPPLY or DEPLOYMENT |
| Event | READINESS, PRODUCTION, CAPACITY, ADOPTION, physical CONSTRAINT, OWNERSHIP or FINANCING_PURPOSE |
| Phase | SOURCE_REPORTED or explicitly FORWARD_LOOKING; no inferred completion |
| Ongoing production | Generic supplies/produces/manufactures needs a change marker or explicit plan |
| Capacity | Requires capacity/facility/fab/plant/factory/campus/production-line context |
| Shared constraint | Explicit shared-market physical supply constraint on an input route; a platform mention is insufficient |
| Price-only wording | Cannot use this new scoped priority branch; retain the separate source-period/commodity comparison and threshold contract |
| Non-events | Uncertain, retrospective and routine notice/guide windows remain background |

Generic FINANCING or AGREEMENT scope is insufficient for this branch; explicit
financing purpose or another supported event is required. The bounded grammar does
not infer operating outcomes, new ownership facts, product compatibility or issuer
orders. Unrecognized syntax remains context, not a reason to invent evidence.

`editorial_priority.scoped` consumes accepted matching traces; it cannot create a
graph route. A rejected scoped trace cannot fall back to generic change words.
Accepted context-only matches retain that conditional relevance flag but can now
produce an editorial signal. Thus relevance uncertainty is preserved without
automatically hiding every source-backed development.

Legacy paths now use `operating_developments` and
`config/operating-developments-v1.json`: a bounded action must have an operating
object (capacity, demand, financing, cost or supply), or a structured facility,
compute deployment, financing or integration object. Exact action/object offsets
are relative to the retained source window. An explicit funding purpose is a
forward-looking allocation, not realized capacity. Plans stay plans. Product
definitions, abstract role/influence expansion and deployment demonstrations do
not qualify by change vocabulary alone. Ambiguous/unrecognized clauses stay in
background; relevance and source-backed graph matching are unchanged.

Facility apposition and quantity complements are bounded; passive deployments
need a source auxiliary or explicit by-agent. These are source text signals, not
verified actor identity or semantic completeness. The 40-point entity feature now
requires the same qualifying link, preventing another link from donating it. This
is still relationship context, not proof the named party performs the action.
Legacy price wording is informational context only, never a commodity price alert;
the separate comparable-period and >5% threshold contract is unchanged.

Freshness is checked by the existing feed boundary, including current source poll,
raw revision proof, article-age windows, profile pins, withdrawals and graph validity.
An editorial assessment in an archival review is **content priority**, not proof
that the article belongs in today's feed. Research archives stay separate.

API traces include event, phase, route role/intents, original source window and
eligibility/withholding reason. Feed UI explains scoped priority and labels future
plans in Vietnamese. Financial direction, magnitude and horizon remain UNKNOWN;
delivery remains disabled. There is no calibrated impact probability or learned
weight claim.

Validation: renamed actors and memory/cooling products; ongoing/retrospective/
recipient/uncertain counterexamples; wrong intent and altered source; shared physical
constraint versus price-only language; RSS/article parity; stale-source, expired-edge
and withdrawn-profile checks. See `reports/editorial-priority-review.json` and the
latest checkpoint for exact CI results and exposed regression metrics.

Opt-in local workspace: `source-cache/operating-priority-workspace-2026-11-28.json`.
Private sources/profiles/labels/DB remain local. No public release is authorized.
See the latest checkpoint and `reports/operating-priority-review.json` for exposed
regressions, unused RSS review limitations, remaining losses and exact CI results.
Keep precision and recall costs visible: stricter priority is not an accuracy gain
when useful developments move to background. Next coverage should address common
operating improvements, supply access and agreements through typed evidence, not
per-company rules or weight changes that conceal missing semantics.
