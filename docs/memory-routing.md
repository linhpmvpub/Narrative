# Sourced memory-company routing — 2026-11-27

The compact company database now has executable MU manufacturing, product-readiness,
materials, customer-agreement and competitor routes. SNDK adds Consumer/Edge product
releases and explicitly scoped flash-market adoption. Narrative targets are unchanged.
Detailed source quotes, profiles, articles, labels and databases remain local.

## Contract

- Six MU bindings extend the two existing ones; two SNDK bindings extend two existing
  ones. Two directed competitor-to-memory edges reuse the issuer's disclosed competition
  evidence. The original company-to-peer relationships remain. Paths use at most two hops.
- Own developments require a sourced company name and product/market plus activity in
  the same sentence. Manufacturing alone is not a new development. Arbitration/litigation
  is excluded from operational agreement routes. This exclusion does not claim legal
  developments are irrelevant to every possible narrative.
- Shared-market and competitor routes remain context-only. An external agreement is not
  a Sandisk customer order; competitor releases do not establish Micron share loss.
  The compound scope “memory and storage” is supported; generic storage in a server
  portfolio description is insufficient for the new flash-adoption route.
- Existing relationship validity, source integrity, review windows and withdrawal apply.
  Node display names can be short sourced names without changing CIK or legal identity.
  No new article-specific fact is added to force a match.

## Opt-in routing guards

`FactorBinding.routing_guards` accepts a bounded unique list with explicit narratives.
The field is omitted when empty, preserving old serialized profile hashes. Guards and
the underlying matching groups must succeed in the same source window. Titles may
constrain market scope but cannot donate positive body evidence. Returned matches carry
`routing_guard_trace`, including version, checks, exact evidence spans and window text.
Rejected windows produce no card; the standalone guard assessment explains the rejection.

| Guard | Required boundary | Current application |
|---|---|---|
| `INFRASTRUCTURE_FINANCING` | Financing activity plus an infrastructure asset/capacity in the same window; reject denial/speculation | NVIDIA sector financing |
| `SERVER_COMPONENT_MARKET` | Automotive/handset context requires explicit server-market evidence in that window | Dell input resilience |
| `SECTOR_CONSTRAINT` | Explicit shortage, disruption or cost-pressure wording; a bilateral supply agreement alone is insufficient | AMD sector rack constraints |

The structured NVIDIA deployment and financing rules are split so financing restrictions
do not accidentally filter deployment assertions. Policy version6 keeps all numerical
weights and priority thresholds unchanged. Financial magnitude, direction and company
impact lag are not inferred by these guards.

These are bounded English rules, not a causal/recipient parser. Asset co-occurrence does
not verify a funded recipient, and constraint wording does not prove industry-wide scope.
Mixed clauses, negation scope, paraphrases and the first eligible window remain limitations.

## Paired exposed regression

All comparisons use the immediate previous profiles and candidate under one runtime,
identical narratives and original labels. Previous memory predictions are also checked
against their original freeze. Original 19 older receipts plus three recent packet/label
sets are reverified. Failed candidate iterations remain local. No fresh blind review,
human gold, random-market estimate, historical as-of replay or automatic promotion.

| Cohort | Previous TP / FP / FN | Candidate TP / FP / FN |
|---|---:|---:|
| Memory complete articles, 150 pairs | 13 / 3 / 25 | 27 / 0 / 11 |
| Older RSS, 1,716 pairs | 54 / 3 / 42 | 54 / 3 / 42 |
| Older filing excerpts, 300 pairs | 5 / 0 / 7 | 5 / 0 / 7 |
| Older complete articles, 150 pairs | 22 / 1 / 6 | 23 / 3 / 5 |
| Recent RSS, 216 pairs | 5 / 0 / 2 | 5 / 0 / 2 |
| Recent complete articles, 30 pairs | 2 / 0 / 0 | 2 / 0 / 0 |

Memory relevance precision81.25%→100%, recall34.21%→71.05%; MU0/10→10/10
positive pairs found and SNDK4/8→8/8. Five unresolved relevance labels remain; selected
unresolved1→0. The 15 lexical clusters include a shared investment family (14 family
components), so these small correlated results are development evidence only. Main
priority against relevance improves4TP/1FP→7TP/0FP but still misses31 relevant pairs.
No price/policy/disruption references in this cohort.

The older full-article set gains one SNDK true positive but adds two MU competitor
matches labeled NOT_RELEVANT in the preserved reference. They remain counted as FPs;
their new sourced competitor path does not authorize relabeling. Main-priority true
positives remain12 (zero FP). An initial loss was traced to missing explicit power-delay
vocabulary and corrected with a general infrastructure-delay constraint, preserving the
failed run. No claim of globally improved precision. The two additional reference FPs
still block release acceptance.

## Local handoff and next work

Workspace: `source-cache/memory-routing-workspace-2026-11-27.json`;
artifacts: `source-cache/memory-routing-2026-11-27/` with final `profiles-v3`, `atlas-v3`,
`registry-v3`, `news-v3.sqlite`, `paired-replay-release`, `broad-replay-release-v2` and pipeline.
Aggregate validation: [report](../reports/memory-routing-regression.json).

Next: evaluate sourced competition versus the precise supply narrative on fresh events;
separate component readiness context from concrete infrastructure demand without losing
useful background; audit priority-window selection before tuning weights. Extend independent
support for policy, price and disruption groups. Keep delivery disabled and candidate opt-in.

The fresh local RSS snapshot contains no MU/SNDK cards; those route demonstrations use
archived full-body replay, without changing publication dates or bypassing freshness.

Validation:47focused tests; exact-commit CI1336SQLite+1336PostgreSQL, migrations,
lint/types/JS, dependency audit and actual-model smoke passed. Desktop/mobile smoke
passed. [CI run](https://github.com/linhpmvpub/Narrative/actions/runs/46015108381)
verifies code commit `d13b28a3a3464df9db0cffdf2ce713803219999d`.
