# Component, application and infrastructure applicability

The optional `FactorBinding.market_scope` declares the market targeted by a
reviewed profile rule: `COMPONENT_MARKET`, `APPLICATION_SOFTWARE`, or
`INFRASTRUCTURE_DEMAND`. It requires explicit narratives and an activity rule.
Existing source evidence, lifecycle, graph path and two-hop core checks still apply.
Absent fields serialize exactly as before, preserving historical profile hashes.

`engine.news_applicability` records literal domain evidence and exact offsets. A
component/application story can support an infrastructure-targeted rule only when
the same sentence contains an explicit infrastructure assertion: hardware orders,
installation/deployment (including announced quantified power capacity), increased
compute demand/capacity, or a reported change in server prices. Memory capacity,
software capability and moving simulation onto GPUs alone do not establish demand
for additional infrastructure. Negation, hypothetical/conditional capability and
rumor wording suppress that bridge. Announced deployment is still an announcement,
not proof of completion, orders, profit or magnitude of company impact.

The title may constrain a sentence but cannot donate a positive assertion to it.
Trace offsets identify the original match and, separately, the exact window used
for the bridge. The card explains target market, detected wording and bridge.
Unknown wording retains legacy behavior. Component and application paths remain
eligible; this is an opt-in path applicability check, not a global article filter.
Core policy version5 changes no numerical weights. Financial impact stays UNKNOWN.

## Local database candidate

The November27 candidate applies the field to two NVIDIA shared-market rules, its
AMD competitor-product rule, one DELL deployment rule and a new Google TPU competitor
rule. It adds a sourced product/competition path, not a title exception. Evidence:

- [NVIDIA annual filing](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm): existing captured competitive scope.
- [Alphabet annual filing](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm): Google within the Alphabet group.
- [Google TPU explanation](https://blog.google/innovation-and-ai/infrastructure-and-cloud/google-cloud/what-is-a-tpu/): Google product definition.

Captured exact quotes/hashes, publication and retrieval times stay local. Group
product context does not merge legal identities or imply customer substitution.
The atlas has6profiles/78nodes/85relations. Existing financial evidence is rechecked,
and the input-market registry is pinned to the new snapshot. Candidate workspace:
`source-cache/market-applicability-workspace-2026-11-27.json`; no default service change.

## Evaluation and limits

See `reports/news-applicability-regression.json`. Previous and candidate profiles
run under the same runtime and unchanged targets. Older RSS, archive and full-body
cohorts are separate; recent exposed cohorts remain separate too. Original labels,
packet hashes and frozen predictions are preserved. These are development regressions
using exposed AI labels, not a new blind evaluation, human gold or historical as-of
backtest. No weight calibration claim follows from the changes.

The initial GPU guard reduced one valid priority match; a generic quantified
deployment assertion restored it. A component filter also initially lost useful
Google TPU context; the sourced competition route restored that context without
claiming NVIDIA customer demand. Both failed intermediate local runs are retained.

Limitations: bounded English vocabulary, sentence splitting and whole-window
negation can miss paraphrases, decimal expressions and mixed clauses. First eligible
window behavior is unchanged. Other bindings can still yield a card, and bindings
without the field retain legacy behavior. This is not a complete semantic classifier.
Remaining false positives, substantial recall gaps and weak MU/SNDK positive support
block promotion. Next: collect unseen group/company-balanced near misses and positives,
then lock/evaluate a new candidate; do not relabel exposed errors or expand regexes
to memorize individual headlines. Data stays local and live notifications stay off.
