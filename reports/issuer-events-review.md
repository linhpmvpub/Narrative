# Shared issuer events — 2026-11-28

Company benchmark **10.64/100**, up **4.14** from6.50 on the same frozen reference.
One additional source-company case is found and correctly prioritized; these are two dimension
improvements on one case, not two recovered articles. No new false positives or regressions.
Legacy score25.18 and all3,240legacy decisions remain unchanged. Current labels are exposed AI
regression, not a fresh independent evaluation or human gold.

| Dimension | TP | FP | FN | Unknown |
| --- | ---: | ---: | ---: | ---: |
| Company relevance | 3 | 0 | 42 | 24 |
| Company attention | 2 | 0 | 21 | 33 |

## Implemented

A versioned eight-contract/seven-family catalog owns issuer-event grammar and business-variable
labels. New families cover financial-performance changes, shipment/delivery/export interruptions
or resumptions, and operating-capacity changes. Existing results, finance, governance and credit
contracts remain. Actor names come from reviewed profiles; there are no ticker or headline branches.

The extractor keeps exact actor/action/object and source-sentence spans, contract/policy identity,
source-reported status and plan phase. It does not calculate financial effect or infer suppliers.
Longer matching contracts and aliases prevent duplicate evidence. Literal subject-object constraints
reject other-company activity, share-price movement, bandwidth/capability prose, questions and
negated or conditional claims supported by the bounded grammar.

Attention eligibility now checks the exact source sentence instead of the entire RSS field.
Uncertainty in an unrelated sentence does not cancel a concrete issuer event; uncertainty in the
same sentence still withholds attention. Tampered windows fail closed. Forward-looking phase is
preserved through assessment; company cards show plans are not confirmed completion.

## Verification

Step1company10.64; step2 and final replay unchanged. No profile, graph or financial observation was
edited.115focused integration tests passed (one existing Starlette warning), Ruff, mypy181files
and JavaScript syntax passed. Exact-code CI46150788978 SUCCESS:2014SQLite/2014PostgreSQL tests;1existingStarlettewarning each; migrations/seed/replay/downgrade,lint/types/JS,both audits and8model smoke cases passed for code22091da6e1cf53827214bcbae2e6e728e57b5fcc.

Isolated local poll:10sources,7OK/3not-modified,1newitem/2revisions. Feed71attention+47background,
one added card, no removals or priority changes among prior cards.8reviewed bodies remain eligible,
8held; no truncation, all deliverydisabled and financial effects unknown. Source poll advanced too,
so the snapshot comparison alone is not a controlled algorithm experiment; the frozen benchmark is.
Desktop/mobile local routed snapshot verifies rendering, filter, token clearing, logout and plan
wording. Default service/tunnel unchanged; no remote availability or7day reliability claim.

## Self-review and next work

The gain is small and direct-issuer only.42company misses remain. Capacity and financial grammars
pass synthetic contracts but do not gain additional measured cases here. One missed result article
uses a short company name absent from the reviewed issuer-name inventory. This is a data gap:
audit aliases with source evidence across companies rather than add a ticker exception or infer
identity by stripping arbitrary words. Older profile scope descriptions also need versioned review
as the generic event catalog grows; source identity is not a newly proven business relationship.

Broader market demand, customer/competitor roles and capital constraints require exact sourced
product/market paths. Do not attach all infrastructure news to every semiconductor company or infer
specific orders. Next audit aliases and exposure inventory, improve common event/role assertions,
then obtain unused complete-source families with frozen predictions before independent AI review.
Keep current labels unchanged and retain all negative controls and group regressions.

This remains a bounded English extractor, not a universal parser. Complex references, hypothetical
or quoted clauses and missing source context can still fail. Human usefulness, explanation fidelity,
causal truth, financial size/horizon and operational coverage remain unmeasured. Company v1 is not
complete. Data/labels/source bytes local; cloud/live notifications/runtime LLM off.
