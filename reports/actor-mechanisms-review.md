# Actor, asset and deployment mechanism review — 2026-11-28

Implemented shared one-hop source references and exact graph mechanism selection for access and financing. Names, evidence and mechanism IDs live in profiles; no ticker/headline branches, changed weights, altered labels or new narrative targets. See [contract](../docs/actor-asset-mechanisms.md).

## Product behavior

Compute buyer/seller/customer references and singular physical data-center references retain original antecedent/current-sentence offsets. Only the immediately preceding sentence in the same paragraph qualifies. Ambiguity, different roles, canceled/negative antecedents, software/conference modifiers, cross-paragraph or title/body donation and chained references are withheld. Full-body and RSS representations share the contract. Reference-derived matches stay background context.

An access rule can pin its exact sourced compute mechanism; the current local rule does so. A revoked selected edge cannot be rescued by another demand edge. Financing requires its own sourced capital/market evidence, exact AFFECTS_DEMAND mechanism and DEMAND/DEPLOYMENT narrative. The parser binds actor, financing action, capital and physical deployment purpose; it distinguishes provider, recipient and arranger without inferring supplier identity, disbursement, completed capacity or amounts. Funding a cooling startup does not become data-center-project financing or an established supply relationship.

The NVIDIA profile advances 23→24 with one new context-only financing binding and an explicit access-edge pin. All sources, graph nodes/edges, narrative targets and financial observations are unchanged; the five other profiles are unchanged. This is a reviewed data configuration on existing evidence, not a new company-specific algorithm.

## Benchmark after each step

| Step | Improvements | Regressions | Unresolved changes |
| --- | ---: | ---: | ---: |
| Typed source references | 0 | 0 | 0 |
| Exact mechanism and project financing contracts | 0 | 0 | 0 |
| Reviewed profile bindings | 0 | 0 | 0 |
| Final hardening | 0 | 0 | 0 |

All relevance and priority decisions across 3,040 exposed AI-labelled pairs and ten cohorts match the original task baseline. **No measured accuracy gain is claimed.** Full group/company aggregates are in the companion JSON. The profile step uses a later replay instant; final hardening uses that same instant. Targets, labels and prior runs are preserved.

infra160 remains 14TP/0FP/9FN for relevance, with 20 unresolved; priority remains 5TP/0FP/4FN, with 21 unresolved. Relevance misses are AMD1/DELL1/NVDA7; all four priority misses are NVDA. Existing older false positives/unresolved labels remain, and three older cohorts have no priority labels. This is not fresh blind, human-gold or causal-impact validation.

## Local feed and validation

The first isolated pipeline result withheld all context cards after source freshness expired. It is retained. An authorized public RSS refresh made ten attempts: eight OK, two NOT_MODIFIED, three new items and zero revisions. The refreshed feed contains 50 main and 44 background cards, with no truncation; all have delivery disabled and financial direction/magnitude/horizon UNKNOWN. None carry the new reference/financing trace in this snapshot. New capability is demonstrated by synthetic integration tests, not by claimed live-feed improvement. New collection/freshness clocks mean this is not an algorithm-only feed comparison.

The local atlas/registry was rebuilt with six profiles, 85 nodes, 103 relations and 11 narratives. Thirteen dated financial sets and four bindings remain; their source bytes and figures are unchanged. Default database/service/tunnel were not changed. No new browser acceptance, latency or seven-day operational claim.

224 final focused tests passed with one existing Starlette warning; Ruff and mypy on 174 files passed. Cases include renamed companies, original spans, full-body parity, unrelated/ambiguous assets, source corrections/withdrawal, an alternative path after exact-edge revocation, and no supply or financial-effect inference. Windows sandbox fixture hard-link errors were resolved by host reruns; initial typing/lint failures remain in local failure history. Exact-code CI: PENDING.

## Remaining limitations and next step

The reference grammar is deliberately bounded English; implicit actors, longer discourse and title-summary ellipsis remain unsupported. Existing benchmark misses partly require absent graph evidence or have demand events paired with supply targets. Do not invent demand-to-supply links, lower priority thresholds or change labels to hide these gaps.

Next prioritize **real unused source families and source-backed missing mechanisms**, with frozen predictions and independent review before further grammar expansion. Reconcile narrative intent against graph endpoints separately and retain the old target's failures. Financial magnitude/horizon, causal truth, personal usefulness and release operations remain unmeasured; v1 is not complete. No further weight tuning is justified by this zero-change regression result.

Local root: source-cache/actor-mechanisms-2026-11-28. Manifest: source-cache/actor-mechanisms-workspace-2026-11-28.json. Current benchmark pointer selects its final run and profiles. Detailed sources, labels, predictions and DB remain local; cloud and real notifications remain off.
