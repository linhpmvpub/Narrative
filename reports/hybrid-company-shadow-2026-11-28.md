# Local hybrid company analyst experiment — 2026-11-28

Both model arms failed the accepted-output contract: all proposed relevant outputs were withheld.
The raw hybrid score exceeds the generic model score on this development sample, but this does not
establish a usable product advantage. Keep the production engine unchanged and repair the shared
source-fact / graph interface before the fresh 100-cluster study.

Executable A/B/C development experiment, not a production migration or a fresh blind study.
24 frozen RSS articles × 5 companies = 120 units; the existing exposed AI agreement reference
has a 77/100 ceiling from unresolved labels. Formula COMPANY_EFFECTIVENESS_V1 is unchanged.
Neither score nor source/graph validation establishes financial impact or human usefulness.

| Arm | Gated score | Raw model score | Relevance | Attention | Withheld | p50 / p95 seconds |
| --- | ---: | ---: | --- | --- | ---: | --- |
| A_engine | 10.64 | N/A | 3TP/0FP/42FN/24U | 2TP/0FP/21FN/33U | 0 | Not measured |
| B_generic | 0.00 | 28.41 | 0TP/0FP/45FN/24U | 0TP/0FP/23FN/33U | 53 | 35.5 / 46.3 |
| C_graph | 0.00 | 33.57 | 0TP/0FP/45FN/24U | 0TP/0FP/23FN/33U | 60 | 53.1 / 69.1 |

Before gates, generic B has 19 TP / 20 FP / 26 FN (relevance precision 48.7%, recall 42.2%);
graph C has 25 TP / 22 FP / 20 FN (precision 53.2%, recall 55.6%). Both retain 24 unresolved
reference units. Higher raw recall comes with substantial false matches, below the unchanged
precision target. After gates B withholds all 53 relevant proposals and C all 60; both gated
scores are zero, with undefined precision because no item is selected. Do not call zero FP success.
B has 49 relevance/attention contradictions; C has 40. C also has 49 invalid/ambiguous source
quotations, 36 unsupported actor spans and 20 missing/wrong-company routes; errors can overlap.
These expose model and interface failures, not proof that the entire relationship database is useless.

Both model arms used Qwen3 4B locally, identical model digest/prompt/required-company schema,
temperature 0 / seed 42, 32768 context / 3072 output limits; Ollama 0.40.19, q4_0 KV cache, flash attention,
256 MiB fit margin, one request at a time on a 4 GiB RTX A2000 laptop GPU. The model is a small
quantized hardware pilot, not evidence about all LLMs. B has source and target names; C adds
bounded graph context and exact path validation. Raw scores expose the cost/benefit of gates.

Source/profile/runtime/model/request/response pins and detailed errors stay local in
source-cache/hybrid-shadow-2026-11-28. Only this aggregate, code and synthetic tests are committed.
No provider API charge; electricity/hardware cost unmeasured. Latency is model request time,
not crawler-to-user latency. Context sizes and token use differ between B/C and are recorded.

## Retrieval and interpretation

69 eligible reviewed company_discovery routes, 66 route offers across 24 articles; 3 articles have no route.
This is a company-route slice, not the entire atlas, price-series registry or numerical prior inventory.
Among 45 resolved relevant units, 21 get at least one company route, 10 lose routes to the bounded
retrieval policy and 14 have no lexical hit. Presence is not proof that the correct mechanism
was retrieved. Do not call all 24 missing route offers missing database facts; 14 require a
separate semantic/data audit and 10 are demonstrably retrieval-budget candidates.

Generic or hybrid model judgment is still a proposal. Pilot behavior copied profile evidence
as a news quotation; source/actor/attention checks withheld it. A loose output array also
omitted four targets; named required company keys now enforce coverage, with post-validation.
Initial failed/aborted runs and the slow f16 hardware attempt remain in local failure history.
No labels, reference weights, profile facts or ticker-specific branches were changed.

One identical-request repeat over 5 company units kept relevance/attention and final decisions
unchanged; one quote differed. This is one exposed control, not whole-cohort stability.
Source quotations and the conditional graph scope form the proposed explanation. Raw rationale
is an unverified local draft. Direction, financial magnitude and horizon remain UNKNOWN.

## Validation and next decision

86 focused tests; exact-code CI [46156324690](https://github.com/linhpmvpub/Narrative/actions/runs/46156324690) passed 2053 SQLite and 2053 PostgreSQL tests,
one existing Starlette warning each; Ruff / mypy 184 files, JavaScript, migrations/seed/replay/downgrade,
both dependency audits and 8 spaCy smoke cases passed. spaCy smoke is separate from the actual
Qwen experiment. Runtime commit `ffcde6ad22a580b5845fa70b90d0d159cb774373`. Three immutable benchmark stages preserve
production company 10.64 and legacy 25.18, zero decision changes; quality gate current.

Next: extract source assertions into validated fact IDs before graph interpretation; the analyst
should select fact IDs and route IDs, with code rebuilding citations from the original source.
Keep the event actor distinct from the company affected by it; normalize identities separately
from the literal actor evidence. Relevance and attention need compatible typed states.
Deduplicate repeated database evidence across routes and allocate context across candidate
companies, then improve semantic/alias retrieval and freeze an updated version. These are shared
workflow changes, not patches for particular tickers or articles.
Read-only next-cohort inventory found 266 candidate RSS articles from 830 current rows after fixed-reference
URL/near-text, source and age checks. This does not establish economic independence, fuller-body
readiness or exclusion from every previous development activity. Candidates remain local and unlabelled.
Use unused fuller-source economic clusters before the planned 100-cluster independent AI
evaluation. No per-ticker patches or retrospective relabeling. Check explanation fidelity,
multi-event coverage, correction/withdrawal integration, repeat stability and latency before
any production promotion. Company intelligence first; optional narratives consume it later.
The complete 100-cluster blind study, production agent integration and v1 acceptance are NOT done.
Private data local; main LLM_MODE=none; real notifications and cloud remain disabled.
