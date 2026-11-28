# Company discovery and narrative benchmark — 2026-11-28

Headline development index: **21.82/100**. First readout of locked predictions, two separate AI reviewers; not human gold or product completion.

| Dimension | TP | FP | FN | Unresolved | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| company | 4 | 0 | 24 | 44 | 100.0% | 14.3% |
| relevance | 4 | 0 | 17 | 47 | 100.0% | 19.0% |
| priority | 3 | 0 | 8 | 50 | 100.0% | 27.3% |

The observed 100% precision rests on only four relevant selections and three priority selections. It is not evidence of established market-wide precision; missed positives and unresolved references dominate this sample.

20 RSS articles × 5 companies: 100 company references, 200 narrative references. All references/inputs remain local. Formula was frozen before labels: 40% company F1, 40% narrative F1, 20% priority F1, each multiplied by resolved reference share.

| Company | Company TP/FP/FN/U | Narrative TP/FP/FN/U | Priority TP/FP/FN/U |
|---|---|---|---|
| AMD | 0/0/5/10 | 0/0/4/10 | 0/0/0/12 |
| DELL | 2/0/4/8 | 2/0/4/10 | 2/0/2/10 |
| MU | 0/0/5/9 | 0/0/1/4 | 0/0/0/5 |
| NVDA | 2/0/4/9 | 2/0/3/11 | 1/0/2/11 |
| SNDK | 0/0/6/8 | 0/0/5/12 | 0/0/4/12 |

With this anchor's unresolved labels fixed, the maximum index is 68.0/100 even if all resolved cases were correct. This is an evidence limitation; do not renormalize the predeclared score or silently relabel the anchor.

All 3,040 old narrative/priority decisions unchanged. New fixed suite contains 3,240 pairs in 11 cohorts; the headline uses only the new anchor. Later replays are exposed regression. Company discovery does not remove narrative FP/FN.

Legacy infra160 illustrates the distinction: company proxy 14TP/0FP/2FN/17U versus narrative 14TP/0FP/9FN/20U. That company proxy covers only watched narratives, unlike the new anchor’s direct company references.

Validation: see JSON receipt for exact code SHA and CI checks. Real notifications disabled; source data/labels/predictions local; no cloud deployment.

Limitations:

- RSS excerpts and convenience source quotas; 20 articles are not proven independent economic events.
- Only AI reviewer agreement; disagreements stay unresolved. No human gold or filesystem isolation claim.
- Direct company truth uses supplied dossiers; missing business scope may create common reviewer blind spots.
- Old company metrics only cover watched narrative unions; no market-wide crawler recall claim.
- Company and group positive support is sparse. Scalar cannot certify every ticker or event family.
- Headline replay is exposed regression from now on; compare only identical suite and policy.
- Financial magnitude/horizon, causal truth, personalized usefulness and operational source latency remain unmeasured.

Priority next steps:

1. Create a shared company-candidate layer using explicit issuer identity and sourced product/market/exposure relations before narrative attribution; preserve company-relevant unassigned context without inventing a narrative
2. Collect full article evidence and clearer source-role/product context for unresolved or implicit infrastructure/demand cases; treat updated excerpts as a new source representation and benchmark version, not edited labels
3. Improve common actor/event/product and sourced exposure contracts for infrastructure readiness, memory pricing/volumes and end-market context; no ticker or headline branches
4. Keep this 20-article anchor for same-suite regression, then add fresh diverse positive/negative families and independent labels; human assessment and release operations still pending
