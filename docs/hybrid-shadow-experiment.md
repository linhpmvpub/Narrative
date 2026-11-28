# Local company analyst experiment

This implements the first executable tranche of [the hybrid plan](hybrid-company-agent-plan.md).
Company intelligence is the target; narratives are absent from inputs and decisions. Shadow output
does not write profiles, canonical events, the live feed or notifications. Main `LLM_MODE=none`
remains enforced. Private sources, graph packets, calls and labels stay under ignored `source-cache`.

## What is compared

| Arm | Reader/context | Result |
| --- | --- | --- |
| A_engine | Current deterministic engine and approved profiles | Existing company assessment |
| B_generic | Local LLM, news and company names, no private graph | Raw model judgment and source-validated judgment |
| C_graph | Same LLM/news/company universe plus bounded sourced routes | Raw judgment and graph/source-validated judgment |

The same frozen articles include deterministic nonmatches. Each article is read once per model arm,
with all target companies, independent stateless calls and alternating B/C order. Both use identical
model digest, prompt/schema, seed, temperature and context/output limits. Actual input tokens differ
because graph context is not free. Prompts contain neither labels nor A predictions. The current
24-article/120-company-unit reference is exposed development data, **not a new blind evaluation**.
No event-independent generalization, financial forecasting or human-utility claim follows from it.

## Implementation and evidence boundaries

- `engine/shadow_analyst.py`: strict proposal schema; reviewed issuer scopes and exact exposure plus
  ownership paths; source/review/effective-time checks; lexical reverse-exposure retrieval independent
  of the existing news matcher's acceptance. Up to two exposure routes and one issuer route per
  company, within a 16,000 UTF-8-byte context budget. Complete routes are dropped when over budget;
  evidence is not silently shortened. This simple retriever can miss paraphrases and may distribute
  context unevenly. Selected route IDs, hashes and retrieval overlaps remain auditable.
- `engine/local_analyst.py`: loopback-only Ollama adapter. No DNS host, redirect, environment proxy,
  cloud model or model substitution; model/server identity checked before and after calls. No tools
  or autonomous actions. Strict JSON, complete-response and conservative context-size checks;
  bounded timeout/output. Failed calls are recorded, not replaced with engine predictions.
- `engine/evaluation/hybrid_shadow.py`: immutable source/profile/runtime export, grouped calls,
  predictions saved before reference scoring, per-arm reports, raw-call/token/latency receipts and
  final output hashes. Altered sources, profiles, runtime or experiment pins invalidate reuse.
  A new directory is required for a corrected source/profile/prompt/model experiment.

Validators require complete unique company decisions, exact unambiguous source quotes, actor spans,
allowed graph route/company membership and sourced issuer names. The graph catalog preserves actual
edge direction, conditions, uncertainty and source hashes. A quote/path can still be semantically
misapplied: **structural validation is not verification of causality or a correct analyst judgment**.
The model's rationale is retained only as an unverified local draft. Proposed presentation combines
the source quote and conditional database scope; financial direction, magnitude and horizon remain
UNKNOWN. Numerical financial predictions are not accepted by this first proposal schema.

`COMPANY_SHADOW_V1` attention uses the model's event/phase/negation features under a fixed code policy:
reported developments and explicit plans may receive ordinal attention; speculation/background,
negated activity and unknown/other event families do not receive priority. Issuer3/exposure2/context1
are reading tiers, not learned financial weights. Report both raw and gated B/C judgments to expose
validator and policy costs. Abstentions and withheld outputs count as nonselections for the existing
benchmark, and are separately counted. Missing/failed calls make an entire arm's score unavailable;
there is no partial-cohort score presented as the full comparison.

## Local use

Use a separately started loopback Ollama server with cloud disabled, for example
`OLLAMA_HOST=127.0.0.1:11435`, `OLLAMA_NO_CLOUD=1`, a workspace-local `OLLAMA_MODELS`,
one parallel request and one loaded model. Do not install a system service or open network access.
The selected model must already be downloaded; the adapter itself never downloads or uploads data.
See official [Windows portable installation](https://docs.ollama.com/windows),
[local configuration](https://docs.ollama.com/faq), and [chat API](https://docs.ollama.com/api/chat).

```powershell
.venv/Scripts/python.exe -m engine.evaluation.hybrid_shadow prepare `
  --output source-cache/my-experiment
# Copy the returned experiment SHA; never substitute an unverified directory.
.venv/Scripts/python.exe -m engine.evaluation.hybrid_shadow run `
  --experiment source-cache/my-experiment --sha256 <experiment-sha> `
  --output source-cache/my-experiment-run --model qwen3:4b
```

Omitting `--model` writes an honest unavailable-arm report. A configured but absent model fails
preflight before any private packet is sent. All records remain local. Generic B uses the same
source representations as C, not fuller web pages. Current RSS development inputs are excerpts;
future reviewed-body experiments use the existing substantive-body verification path.

## What remains before production

This is one primary event per company/article, not the complete two-stage multi-event extractor.
There is no semantic retrieval, online queue/cache/retry policy, watchlist delivery, complete
explanation-fidelity label set or human validation. Frozen input replay is not a live revision/
withdrawal integration. Source hashes prevent changed replay; a future live consumer must use the
existing ingestion lifecycle and cancel/reprocess superseded output rather than promote this CLI.

Inspect errors by missing graph scope, retrieval budget, unsupported source/path, semantics and
attention. Then lock a version and collect unused economic clusters before independent AI labeling
(clearly nonhuman). Do not adjust labels or promote a small-model score into release acceptance.
Run both established benchmarks and `quality_gate --all` after runtime/profile updates. Repeat
consistency, cost/latency at workload, source revisions and precision/recall acceptance remain required.
