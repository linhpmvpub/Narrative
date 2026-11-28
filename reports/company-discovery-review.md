# Company discovery and private feed review — 2026-11-28

**25.18/100, +3.36 against the same fixed anchor.** Exposed AI development reference; not market accuracy or product completion. No new blind labels or weight changes.

| Dimension | Found relevant | False positives | Missed | Unresolved |
|---|---:|---:|---:|---:|
| Company | 7 (was 4) | 0 | 21 (was 24) | 44 |
| Narrative | 4 | 0 | 17 | 47 |
| Priority | 3 | 0 | 8 | 50 |

Company recall 14.3% → 25%. Only seven company selections across four positive source clusters support the zero-FP observation. Anchor: 20 articles, 100 company units, 200 narrative pairs; fixed evidence ceiling 68/100. Older 3,040 pairs unchanged. Total suite: 3,240 pairs / 11 cohorts.

## Company diagnostics

| Company | TP | FP | FN | Unresolved |
|---|---:|---:|---:|---:|
| AMD | 0 | 0 | 5 | 10 |
| DELL | 2 | 0 | 4 | 8 |
| MU | 1 | 0 | 4 | 9 |
| NVDA | 3 | 0 | 3 | 9 |
| SNDK | 1 | 0 | 5 | 8 |

## Implementation and observed feed

- Shared issuer/exposure discovery independent of narrative inventory; sourced aliases, exact factor and company-membership paths, read-time reviews/versions and common role/mechanism guards. No ticker or headline exceptions.
- Six profiles including one historical NVIDIA profile; five-company current pilot. 86 nodes, 108 relations, 11 narratives; 69 reviewed discovery rules. Added MU data-center demand evidence and DELL/SNDK product-metric membership. Existing numeric observations/source bytes unchanged.
- Ten RSS polls: eight OK/two NOT_MODIFIED, one new item, no revisions. Final local snapshot: 50 main + 44 background + 22 unassigned company cards. Existing 94 narrative cards carry discovery evidence; no duplicated article-company across sections or truncation. New company section: MU19, AMD1, NVDA1, SNDK1. These are unlabelled feed counts, not 22 proven useful recoveries.
- Directed visual paths, exact source quotations, source links, mobile wrapping, company filter and logout. Headless local snapshot rendering passed at desktop1440×1000/mobile390×844. API/integration tests separately check source/revision/correction/withdrawal/staleness/pinning. This is not remote-service or operational acceptance.
- All116 cards retain disabled delivery and unknown financial direction/magnitude/horizon. No canonical event created from company discovery; no priority promotion. Default running service/tunnel unchanged; isolated manifest records the new workspace.

## Validation and remaining limits

- Local92 integration tests passed; final63 tests and33 focused contract checks passed. Ruff, mypy176files and JavaScript syntax passed. Current private benchmark gate passed after final runtime/data edits. Exact-code GitHub CI passed:1937tests on SQLite and1937 on PostgreSQL, migrations/seed/replay/downgrade, both dependency audits and8actual-model smoke cases. One existing Starlette warning per test suite.
- Failed attempts and superseded roots retained; see local failure-history.json. No unresolved implementation-test failure is concealed.
- Narrow English issuer syntax and source aliases still require reviewed profiles. RSS excerpts can miss context; production full-body company delivery remains future work. Incidental infrastructure prose can create low-value company background; the19MU cards are not independently quality-validated.
- Fixed anchor still misses21company/17narrative/8priority positives, with44/47/50unresolved. Group capacity0TP/5FN, demand1TP/7FN and technology0TP/4FN lack breadth; financing has no positive reference support. Do not interpret aggregate score as uniform quality.
- Next: enrich substantive full-article evidence and bounded product/market scopes, particularly capacity/end-market/memory price-volume families; retain exact-source and conditional exposure limits. Evaluate unused varied event families with separate blind reviewers before calibrating ranking. Personal utility, financial/causal validation, latency/coverage, seven-day reliability and release approval remain open. v1 is not complete.

Code:997e730ce04ae83c00855f25c0a400055efcc8e8. [CI46142500465 succeeded](https://github.com/linhpmvpub/Narrative/actions/runs/46142500465).
