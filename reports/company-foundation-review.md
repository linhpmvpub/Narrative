# Company foundation implementation and independent baseline — 2026-11-28

**Company effectiveness:6.50/100** on a new direct-company target. This is the first baseline,
not a comparable change from the unchanged legacy mixed score25.18. Company reference ceiling77.
The result exposes substantial missed coverage; v1 is not ready for release.

| Dimension | Correct positive | False positive | Miss | Unknown |
| --- | ---: | ---: | ---: | ---: |
| Company relevance | 2 | 0 | 43 | 24 |
| Company attention | 1 | 0 | 22 | 33 |

24unused-source articles/120company units; two independent AI contexts,14relevance and23attention
disagreements. Agreement is not human gold. Predictions/policy were frozen before reviewers;
no post-label matcher edits. Same code replay exactly matches frozen predictions. Future use
of this reference is exposed regression. Company recall4.44%,attention recall4.35% among resolved
positives; zeroFP over so few selections cannot establish precision. Event groups overlap and
no positive input-price evidence supports that family. Economic-period independence is unproven.

## What changed

- Company schema, source discovery, assessment, ranking, API and primary feed work without any
  narrative. All supported binding types can use explicit company-only scope; exact evidence,
  graph membership and timing gates remain. Shared assessment drives production and benchmark.
- Ordinal attention tiers separate issuer/exposure developments from background and sponsorship.
  Conditional business paths and unknown financial direction/magnitude/horizon remain explicit.
  No claim of calibrated impact weights, quantified benefit or predicted share price.
- Reviewed article lifecycle is shared with company cards. Source revision/hash/withdrawal/freshness
  gates fail closed; registered body URLs cannot fall back to stale RSS. All narrative projections
  remain separate. Current reviewed issuer release reaches a company card; its matched evidence is
  the title, so this does not demonstrate new real-news body-only recall.
- Direct-company benchmark freezes source/profile/runtime/predictions, validates distinct reviews,
  preserves unknowns, reports group/company diagnostics and joins the existing freshness gate.
  All3,240legacy pair decisions remain unchanged at each stage and final replay.

## Local integration and validation

120real source-company cases across5profiles keep identical assessment/evidence when all narratives
are removed. Local feed snapshot:70attention+47background;8source bodies valid/8held;1current full-body
card replaces RSS; no truncation, deliverydisabled. A10source RSS poll had8OK/2not-modified and2new items.
Desktop1440×1000/mobile390×844 local routed-snapshot UI checks passed, including no overflow, company
filter, no browser-storage token and logout. Default server/tunnel was not changed or revalidated.

159focused tests passed (one existing Starlette warning); Ruff,mypy180files,JavaScript syntax passed.
Exact-code GitHub CI passed:1,966tests on SQLite and1,966 on PostgreSQL; migrations/seed/replay/downgrade, both dependency audits and8model smoke cases passed. Code3254ba1cf0022ac70b88ec16a03228f6f3082288 pushed; [CI46147209795 succeeded](https://github.com/linhpmvpub/Narrative/actions/runs/46147209795).
Private inputs, dossiers, labels, predictions, logs and source bytes remain local. Only aggregate
results, contracts, code and synthetic tests are published.

## Self-review and next work

The runtime boundary is fixed, but coverage is still constrained by narrow issuer predicates and
uneven product/market mechanisms inherited from earlier examples. Current relevance misses include
capacity15,policy9,technology7,results6,financing5,supply5 (overlapping groups, not a sum). AMD/DELL/MU
have no true-positive selections in this small reference. Source excerpts and shared AI assumptions
also limit the labels; do not expand indirect supplier/financial claims simply to satisfy them.

Next review these as reusable event/role/asset/graph classes. Specify source assertions first,
source missing exposures, then improve common recognition and separate conditional market context
from concrete company developments. Prioritize capacity/delivery/access, results and capital constraints;
keep explicit mitigants and unknowns. Re-run both frozen references after each stage, then collect
unused fuller sources with new frozen predictions and independent labels. Do not tune each headline.

Explanation fidelity, human usefulness, live coverage/latency, financial magnitude/horizon and causal
truth remain unmeasured. Company watchlists, histories, attention controls, acceptance-policy mapping
and operational gates remain open; arbitrary narrative thesis/history/outcome tracking follows them.
Data local; real notifications/cloud/runtime LLM off. No decision from the user is needed for these
next authorized development steps.
