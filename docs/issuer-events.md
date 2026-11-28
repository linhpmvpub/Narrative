# Shared issuer-event contracts

Implemented2026-11-28. This extends [company assessment](company-assessment.md) without requiring
narratives or changing graph membership. The versioned grammar is in config/issuer-events-v1.json;
engine/issuer_events.py applies it to reviewed issuer names from company_discovery rules.

| Family | Source development | Business variable |
| --- | --- | --- |
| FINANCIAL_RESULTS | Reports/announces results | Reported results |
| FINANCIAL_PERFORMANCE | Reports a metric change; issuer metric rises/falls | Source-reported metric |
| SHIPMENT_CHANGE | Halts/resumes/cuts deliveries, shipments or exports | Shipment activity/market access |
| CAPACITY_CHANGE | Expands/builds/closes/reduces specified operating assets | Operating capacity |
| FINANCING | Raises/refinances specified funding | Financing |
| GOVERNANCE | Appoints/removes named executive/board role | Governance |
| CREDIT_RISK | Issuer credit rating/outlook change | Credit access |

Names and aliases must be sourced profile data. Event predicates and bounded object grammar are
shared; no company/ticker/literal article exceptions. New patterns require an explicit issuer as
the grammatical subject or owner of a metric. They do not borrow actors from another field or
resolve unstated customers/suppliers. Mention-only, stock-price movement and product capability
are distinct from operating developments. Unrecognized text remains unmatched; this is not a
universal parser or a claim that no event occurred.

Each match preserves the original text and field-relative actor/predicate/object/source-window
spans, contract id/policy digest, event family, business variable, source-reported status and phase.
The four legacy contracts may lack structured predicate/object spans; absence is explicit. The
longest contained match wins so overlapping aliases/general results do not count twice. Separate
noncontained events remain separate evidence. No amount, comparison period, inferred margin,
financial magnitude/horizon or stock-price direction is invented.

Explicit plans/to/will in operating-action contracts carry FORWARD_LOOKING. They can be relevant
and worth reading while still uncompleted. Source-reported means the source makes the claim,
not that its truth, timing or financial effect has been independently verified. Existing uncertainty,
routine and retrospective attention guards remain. Assessment validates the exact event sentence;
unrelated sentences do not supply or veto its evidence. A same-sentence uncertainty still holds
attention. Cards expose plan status and unknown financial consequences.

Synthetic tests use renamed companies, positive actions and adversarial other-subject/negation/
question/cross-field/capability/share-price cases, plus exact offsets, alias deduplication, source-window
tampering and phase propagation. Both frozen benchmarks run after each logical update. Current
same-reference gain is one issuer case recovered for relevance and attention; capacity/financial
performance have not yet shown measured gains. See [review](../reports/issuer-events-review.md).

Next improve source-backed alias inventory and typed graph exposure separately from grammar.
Future additions must specify source subject/action/object/phase, retained negative controls and
business-variable scope before implementation. Do not weaken source/version/withdrawal/time gates,
retag unknown financial fields as low impact or create a customer relationship from a headline.
