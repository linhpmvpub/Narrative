# Source references and exact deployment mechanisms

This extends the existing ingestion → reviewed profile → graph → narrative → card flow. It does not create canonical facts, add a customer/supplier from an article, change scoring weights or enable delivery.

## Typed source references

`source_references` resolves one typed reference from the immediately preceding sentence in the same paragraph. Compute buyers/sellers/customers must have a literal profile company antecedent with the same role. A singular data-center antecedent may resolve “the/this/that facility/site”. Original source spans, paragraph offsets and the resolution basis remain in the trace; the text is never rewritten.

There is no headline/body donation, chained reference, intervening sentence, cross-paragraph lookup or generic company pronoun inference. Multiple candidate parties/assets, denial, canceled/hypothetical antecedents and an asset used as a software/conference modifier are withheld. Full-body source context must match the supplied sentence and offset exactly. This bounded English grammar is not general coreference resolution.

Access references and resource-readiness references remain context-only/BACKGROUND. A buyer reference is not verified legal identity; an asset reference is not evidence of the profile company's participation or a realized incident. Readiness still requires its exact sourced resource mechanism.

## Exact access and financing paths

`AccessConstraintRule.relationship_id` optionally pins an existing sourced AFFECTS_ACCESS/AFFECTS_DEMAND edge from the bound factor. The current local access profile is migrated to this explicit pin. Legacy profiles without the optional field keep their previous representation and contract. A different valid demand path cannot substitute for a revoked or expired pinned edge. The edge also needs its own compute evidence; narrative intent remains DEMAND/DEPLOYMENT, not SUPPLY.

`FactorBinding.project_finance.relationship_id` is opt-in and required for financing matches. The binding and selected AFFECTS_DEMAND mechanism each need literal capital/data-center evidence and a declared narrative policy. Overlapping matcher overrides are rejected. This is a conditional physical deployment path; it does not make a technology startup an established supplier.

The source sentence must connect a named actor, financing predicate, capital and a physical deployment purpose. Actor roles distinguish capital recipient, provider and arranger. A one-hop asset reference is allowed with separate antecedent provenance. Other clauses, software, conferences, lawsuits, cooling-component funding and unsupported syntax cannot supply a facility-project object. Source claims of financing remain distinct from disbursement, completed capacity and orders. Amounts are not extracted by this matcher. New financing routes remain context-only.

Existing editorial capital-backing classification is unchanged: it still needs an independently eligible graph/narrative route. No demand-to-supply edge is invented to satisfy a benchmark label.

## Evidence and validation

The local profile update reuses previously captured, hash-verified primary evidence and existing mechanisms; no graph nodes, edges, narrative targets or financial observations change. The current suite has 3,040 exposed AI-labelled pairs. Run it after code, profile and final hardening updates, preserving all runs and the task-start comparison. A zero-change result is reported as no measured quality gain, not as proof of generalization.

Tests cover renamed synthetic companies, source/body parity, original spans, ambiguous and unrelated assets, no chained references, exact-edge withdrawal with an alternative path, financial/supply boundaries and RSS correction/withdrawal. Private sources, DB, predictions and labels stay local. See [review](../reports/actor-mechanisms-review.md).
