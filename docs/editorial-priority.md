# Editorial priority for scoped developments

The engine answers two separate questions: is this news related to a narrative,
and does the supplied source describe a concrete development worth highlighting?
Neither answer establishes financial impact or authorizes a notification.

`config/editorial-priority-v1.json` is the versioned contract. Actor names, products,
relations and narrative intent remain source-backed profile data; there are no
ticker, publisher or headline exceptions. Core policy12 retains numeric40/30/20/20
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

Legacy non-scoped change-word and structured-activity branches still run with shared
routine/uncertain/retrospective exclusions. They remain an observed limitation:
four generic change-word paths and one legacy compute-deployment path account for
the five unchanged priority false positives on the exposed framework reference.
Do not call those branches fully standardized or add exceptions for those articles.

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

Opt-in local workspace: `source-cache/editorial-priority-workspace-2026-11-28.json`.
Private sources/profiles/labels/DB remain local. No new blind evaluation or public
release acceptance is claimed. Next: migrate legacy priority to explicit action/object
and operating-purpose scope, then freeze unused publisher/family-diverse events
before independent reviews; keep original labels and all observed failures.
