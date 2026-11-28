# Direct-company quality benchmark

Version: COMPANY_EFFECTIVENESS_V1, first reference 2026-11-28. This is a development index
for company news discovery and attention, independent of example narratives. It is neither
impact probability nor percent product completion. The legacy mixed40/40/20 suite remains
unchanged and must also pass its freshness/regression check.

## Frozen target and scoring

Before independent review, freeze exact source-company units, source provenance, current
profile/runtime hashes, predictions, review packet and policy. Reviewer packets contain the
source text, sourced company dossiers and rubric; no predictions, matcher rules, narrative
targets or peer labels. Two distinct AI contexts label relevance and company attention plus
article-consistent event groups. These are AI references, not human gold.

Require complete unique labels, matching packet hashes, valid relevance/priority combinations,
article-consistent groups and distinct reviewer identities. Preserve exact agreement; different
answers become INSUFFICIENT_CONTEXT. Unknown is not negative. Group disagreements become UNKNOWN.
No root-agent adjudication or post-label matcher tuning was used for the first baseline.

For dimension d, let R_d be its resolved fraction and F1_d = 2TP/(2TP+FP+FN).

`score = 100 × (0.60 × F1_relevance × R_relevance + 0.40 × F1_attention × R_attention)`

The weights were declared before labels; they are reporting weights, not runtime relevance
weights. If either dimension has no resolved positive support, score is unavailable. Report
reference ceiling = 100 × weighted resolved fractions, but do not rescale the score upward.
Keep TP/FP/FN/unknown, company/group counts, positive source clusters and changed decisions.
Only identical freeze/reference/policy permits comparable deltas. Different score definitions,
samples or reference versions are separate series, never algorithm improvement by themselves.

## First reference and limits

24 previously unused source articles × five companies = 120 units. Selection excluded old
suite URLs and near-duplicate text using a fixed trigram threshold. It did not establish
independent economic periods. Generic sampling strata had four articles each in results,
finance, capacity, demand, policy and other; these sampling hints are not reviewer labels.
The reviewers found no positive input-price support; explanation fidelity, causal truth,
financial magnitude/horizon, human utility and internet coverage/latency remain unmeasured.

| Dimension | TP | FP | FN | Unknown | Recall among resolved positives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Company relevance | 2 | 0 | 43 | 24 | 4.44% |
| Company attention | 1 | 0 | 22 | 33 | 4.35% |

First score **6.50/100**, reference ceiling **77.00/100**. Reviewer disagreements:14 relevance,
23 attention. Zero false positives over two/one positive selections cannot establish good
precision. The old mixed index remains25.18/100; this is not a drop from25.18or a comparable
change. All3,240old pair decisions remain unchanged. The new reference is now exposed and
must be called regression on future tuning; acquire unused source/event families for fresh review.

## Local artifacts and required workflow

Current pointer: source-cache/quality-benchmark-current.json. Its company_benchmark member
contains freeze/freeze_sha256, reference/reference_sha256, profiles and run. Detailed articles,
labels, dossiers, predictions and receipts stay ignored/local. Publish only code, synthetic
tests, policy and aggregate results. Current private root: company-foundation-2026-11-28.

Freeze/reference APIs live in engine.evaluation.company_benchmark. Replay the preserved
company pointer into a new output directory:

```powershell
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/python.exe -m engine.evaluation.company_benchmark run --pointer source-cache/company-foundation-2026-11-28/company-pointer.json --output source-cache/NEW-company-run
.venv/Scripts/python.exe -m engine.evaluation.quality_gate --all
```

Also replay the legacy suite with its pinned suite SHA, profiles and baseline. Inspect both
reports and all changed decisions before advancing pointers; the command does not advance
pointers automatically. Keep the company_benchmark member in the combined pointer. Re-run
both after each logical runtime/config/profile update; after the last change require both
freshness checks. Reference/source/review/output tampering or changed runtime/profile hashes
must fail closed. New targets/labels/policy require a new immutable reference version.

Synthetic CI validates benchmark behavior but cannot run the private corpus. Exact-code CI
and local benchmark receipts prove different things; neither is human usefulness or release
acceptance. Existing numerical quality/reliability gates have not been lowered or passed.
