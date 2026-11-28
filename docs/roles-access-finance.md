# Graph roles, access restrictions and capital backing

Implemented in three measured steps (2026-11-28). This extends the existing
source → versioned profile → graph → narrative → editorial card flow. It creates
no canonical customer/supplier transactions, legal conclusions or financial forecasts.

## Non-exclusive roles

`relationship_roles.roles` derives roles from current, sourced, incident graph
edges with direction, scope and source IDs. COMPETES_WITH, BUYS, SUPPLIES and
SELLS are separate statements. One node can have several roles. Node kind or a
matched name cannot assign a role; product competition does not establish a
company-wide identity or a customer's supplier for a particular project.

Infrastructure scope v2 therefore allows a known competitor's **project-operator**
statement as conditional market context when technology is unspecified. It does
not invent a customer or order. Explicit other-vendor technology stays restricted;
a named third-party project collaboration stays bounded to its participants
unless the profile company is independently present. Collaboration remains a
conservative boundary, not proof of an exclusive supply agreement. The trace
records non-exclusive graph roles separately from source actor/technology spans.

## Access constraints

An optional `FactorBinding.access_constraint.company_terms` enables the shared
classifier on an explicitly reviewed company/compute binding. Terms must be
sourced and belong to the profile's legal/company names. No simultaneous matcher
scope/guard may be bypassed by this override. Existing source revision, profile
review time, entity checks and graph validity remain upstream requirements.

The source must connect compute resources to a restriction of **access**, or an
explicit exclusion requirement for purchasing/accessing those resources. The
company's product/buyer/seller reference must occur in that same clause. An analyst
mention, another clause, building-entry restriction, denial or hypothetical is not
enough. Current bounded grammar may withhold complex valid syntax; it is not a
complete legal-policy parser.

Routing requires declared DEMAND/DEPLOYMENT intent and a sourced AFFECTS_DEMAND
or AFFECTS_ACCESS path, without competition substitution. This implementation
does not turn demand-side access restrictions into supply effects. A new source
claim never creates a graph edge. Priority uses the same revalidated source
assertion and records SOURCE_REPORTED_REQUIREMENT or an explicit plan.
Legal status, actor identity, orders and financial effect remain unverified.

The first real binding uses an existing reviewed compute-access factor and demand
edge; only its profile/binding version changes. Numeric impact assumptions and
narrative targets do not change. More companies require their own reviewed data
scope; broadening the engine's ticker vocabulary is not the expansion mechanism.

## Capital backing

`capital_backing.assess` only consumes a window that already has a valid narrative
match. A backing/funding predicate must have a direct operating counterparty and
a same-clause development/manufacturing/building purpose linked to a physical
operating asset. Lawsuits, conferences, general software, hypothetical support
and unrelated clauses cannot supply that purpose.

SOURCE_REPORTED_BACKING differs from FORWARD_LOOKING plans. Neither means capital
was disbursed, the financed capacity was delivered, or the counterparty is a
customer. Amounts in another headline/summary are not borrowed; this parser does
not extract amounts. It changes editorial eligibility only, not graph ownership,
relevance, company impact direction, financial magnitude or horizon.

## Measurement and boundaries

Run the pinned [quality benchmark](quality-benchmark.md) after each step and again
after final hardening. Preserve the original references and all intermediate runs.
Compare exact changed decisions, not only net metrics. Current-profile replay with
a new database version uses an explicit new replay time; later code-only steps use
that same time. Exposed AI references are not a new blind evaluation or human gold.

Live delivery/cloud remain disabled. Existing product acceptance gates are unchanged.
See the [step-by-step report](../reports/roles-access-finance-review.md) for measured
gains, remaining misses, unmeasured dimensions and the next shared-framework work.
