# Infrastructure development and operating-purpose contracts

## Participant and vendor scope — 2026-11-28

Optional `FactorBinding.infrastructure_scope` declares sourced `own_names` and
competitor names attached to existing `COMPETES_WITH` relationship IDs. It applies
only to the v2 infrastructure rule. Names must occur literally in binding evidence;
competitor names must also occur in the referenced edge evidence, which must touch
the company or one of its directly sold products. The own-name list must include
the profile company name. This is reviewed applicability data, not entity proof.
Legacy profiles omit the field and keep their serialization and behavior.

The shared `infrastructure_scope` parser distinguishes:

| Source scope | Treatment on an existing demand/deployment route |
|---|---|
| Generic operator or market buildout, no scoped vendor assertion | Conditional market context; beneficiary/vendor remains unknown |
| Sourced company explicitly acts or participates in the project | Conditional own participation; no inferred customer/order |
| Sourced competitor acts/participates, without target participation | Withhold this general demand route; other independently supported bindings remain eligible |
| Asset explicitly powered/built with another vendor's technology | Withhold; being an operator does not prove use of the target company's technology |
| Explicit target technology or joint target participation | Keep the conditional path when supported; never assert exclusive supply |
| Another clause, title mention, analyst affiliation, or unrelated asset | Cannot donate a participant or technology owner |

The parser uses exact source spans, bounded active/coordinated subjects, limited
project-work phrases and explicit technology connectors. Capitalized unknown vendor
names in `powered by`, `built with/using` or `based on` claims can constrain scope
without inventing a database entity. It does not understand every passive,
possessive, alias or cross-sentence form. A company name alone is not a role.
Competitor references are checked against source status, knowledge and validity
time; missing context or an expired scope is withheld. Source, revision, withdrawal,
freshness and route validity still apply upstream. A rejected sentence cannot hide
a later independently eligible sentence, or borrow a positive headline.

Accepted trace/explanation reaches RSS and reviewed full-body cards through their
shared matching API. Source actor identity, orders and financial magnitude remain
UNKNOWN/unverified. Numerical priority weights are unchanged. Changes to company
coverage are reviewed profile versions, never ticker/headline branches.

See `reports/infrastructure-scope-review.json` and the latest checkpoint for
exposed regressions, separately frozen new AI reviews, remaining errors and CI.
Local workspace: `source-cache/infrastructure-scope-workspace-2026-11-28.json`.

The engine surfaces conditional research context through existing sourced profile
routes. A data-center story does not establish a company customer, hardware order,
commercial capacity, or financial impact. This contract separates missed routing
from missed editorial priority; numerical weights remain unchanged.

## Opt-in profile and graph scope

`ActivityRule.version=activity-assertions-v2` with market `DATA_CENTER` and event
`INFRASTRUCTURE_DEVELOPMENT` enables the shared parser. It requires explicit
narratives and literal data-center evidence in the binding. Names and eligibility
remain profile data; no ticker or headline is an engine branch. Existing v1 rules
and serialized profiles remain valid.

`MARKET_DEVELOPMENT_CONTEXT` requires a declared DEPLOYMENT or DEMAND intent and
an eligible source-backed graph path. A competitor edge or a SUPPLY-only target
cannot be repurposed as general infrastructure demand. Missing routes stay missing;
do not rewrite old targets or create a supply effect to satisfy reference labels.

The current local migration adds two bindings to existing demand paths, changes no
relationships or narrative targets, and produces new immutable profile/atlas/input
registry versions. Original source quotes and financial periods remain unchanged.
Other companies receive no new binding without appropriate sourced applicability.

## Source and event interpretation

`config/market-developments-v1.json` declares source asset/action classes, a
1200-character sentence limit, a 180-character object bound, clause boundaries and
nonassertion exclusions. The action must govern the infrastructure object in the
same clause. A title or other sentence cannot donate a missing positive assertion.
Purpose infinitives require an explicit decision predicate; abstract influence,
marketing, component demonstrations and objects merely located in data centers
cannot qualify as infrastructure construction.

| Source development | Phase / editorial treatment |
|---|---|
| Operator/business background | BACKGROUND; related context only |
| Explicit proposal, filing or plan | FORWARD_LOOKING; not completed capacity |
| A planned pilot or test | EXPERIMENTAL_PLAN; not commercial operation |
| Source-reported pilot or test | EXPERIMENTAL_ACTIVITY; commercialization unknown |
| Explicit operating action | SOURCE_REPORTED_ACTIVITY; not independent verification |

Every accepted trace retains source text and relative action/object offsets.
Priority reparses the original source window to reject altered traces. Current
revision/capture proof, profile pins, validity/withdrawal and source freshness
remain enforced upstream. Historical content does not become fresh news.

## Supply funding and customer agreements

`operating_purposes` consumes an already matched sourced path. It recognizes
bounded input-processing/manufacturing investment, explicitly changed access to
materials, and completed/signed/announced customer or supply contracts. These are
separate events: allocation is not production; a contract is not delivery.
Shares, unrelated assets, general corporate finance, conferences and descriptive
contract benefits cannot donate an operating purpose. Clauses cannot lend objects
to one another. No counterpart, amount, terms, margin or impact horizon is inferred.

Vietnamese feed labels distinguish experiments, allocations and agreements. All
financial effects remain UNKNOWN; delivery stays disabled. Commodity price alerts
retain their separate comparable-period and >5% threshold requirements.

## Evidence and limits

Tests cover renamed companies, unrelated markets/objects, proposals versus
purposes, planned tests, background, literal evidence, route intent, expired edges,
withdrawal, funding and agreement counterexamples. Existing AI-labeled cohorts,
including the previously blind 120 pairs, are now exposed regression data.
See `reports/market-purpose-review.json` and the latest checkpoint for exact
measurements, failures and CI. No new independent accuracy or public release claim.

The grammar is deliberately bounded: complex nominal/passive forms and ambiguous
cross-field references remain incomplete. Broad market context does not identify
the technology vendor. Scope disputes require sourced graph/narrative review,
not numerical weight changes. Further generalization needs an unused-family
prediction freeze and independent labels after the implementation is stable.

Local manifest: `source-cache/market-purpose-workspace-2026-11-28.json`.
Raw sources, labels, profiles and databases remain ignored and local. Default
service/tunnel configuration is unchanged.
