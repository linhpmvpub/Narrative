# Hybrid company-news agent: assessment and experiment plan

2026-11-28. Requested evaluation of an analyst agent using the project's relationship/impact
database, algorithms and weights. This is a proposed experiment, not an implemented LLM pipeline,
measured improvement, production migration or authorization to transfer private data to a provider.
Company intelligence remains primary; narrative remains an optional downstream product.

## Recommendation and observed baseline

Prefer testing one bounded analyst role inside a reproducible workflow over continuing to make
phrase patterns the main semantic reader. Reuse the source lifecycle, graph, evidence, evaluation
and delivery-policy code. The hypothesis is better paraphrase/role/negation/phase interpretation
and more useful explanations; it has not yet been measured for this project.

Repository evidence:

- engine/settings.py rejects LLM_MODE values other than none. Existing model smoke uses the
  optional local spaCy dependency parser, not a generative LLM or production analyst agent.
- Current direct-company benchmark is10.64/100:3TP/0FP/42FN/24unknown relevance and2TP/0FP/21FN/
  33unknown attention, across24articles/120company units. This is an exposed AI development
  index, not10.64%accuracy. Few selections make zeroFP weak evidence of precision.
- Seven issuer-event families/eight grammar contracts and sourced graph scopes exist. Five
  current pilot profiles plus one historical profile have86nodes/108relations. Identity,
  product/market exposure and source completeness gaps remain. An LLM cannot validate a
  missing relationship merely by producing a plausible story.
- Primary company attention currently uses ordinal tiers, not empirically calibrated financial
  impact coefficients. Benchmark60/40weights are reporting weights and must not be reused as
  business-impact weights. No claim that the current database alone is a proven competitive moat.

[Anthropic's workflow guidance](https://www.anthropic.com/research/building-effective-agents)
distinguishes fixed workflows from autonomous control and recommends adding complexity only
when it improves measured results, noting cost/latency tradeoffs. The original
[RAG research](https://arxiv.org/abs/2005.11401) supports studying generation with retrieved external
knowledge; its QA results do not demonstrate financial-news accuracy for this engine. The proposed
architecture below is our application-specific inference, not an externally validated recipe.

## Proposed flow and ownership

1. Collect official filings/issuer disclosures and current public RSS/article sources; preserve
   publication/availability/capture times, source bytes, hashes, revisions and withdrawal status.
   Process authoritative source records before aggregate commentary where available. Existing
   X adapter remains contingent on actual API access; this assessment does not enable it.
2. Deduplicate source versions and cluster likely event rewrites while retaining independent
   provenance. Corrections/supersession trigger invalidation/reprocessing. Do not merge contradictory
   facts merely because their headlines are similar. Collections run independently of inference.
3. The same analyst role extracts a typed event proposal: source assertion, actor/object/product,
   event family, attribution/negation, plan versus reported activity, geography, period and quantities
   exactly as supplied. One article can contain multiple events. Missing fields remain unknown.
4. Retrieve candidate entities and relevant database neighborhoods through read-only tools.
   Use alias/product/material/market indexes, optionally semantic retrieval after local evaluation.
   Search reverse exposure paths as well as named issuers, so unnamed affected companies can be
   considered. A shallow scoped graph packet contains exact edge IDs, sources, effective/known
   times, conditions, exposure parameters, mitigants and uncertainty, not the entire database.
5. The analyst selects supported candidate paths and describes conditional business channels.
   It can request bounded additional retrieval or return INSUFFICIENT_CONTEXT / MISSING_DB_SCOPE.
   Retrieval includes the existing deterministic candidates but is not restricted to articles
   accepted by today's matcher; otherwise the old false negatives remain invisible.
6. Code validates source quotations/spans, entity IDs, exact graph/member paths, temporal/version
   compatibility, allowed inference bounds, units/periods and policy. Only source-backed numerical
   relationships or explicitly governed prior scenarios can enter calculations. Invalid proposals
   are withheld; a failed model attempt does not silently become an unrelated trusted result.
7. Deterministic assessment computes versioned features/attention policy and novelty/dedup rules.
   The agent drafts a short source-grounded explanation from the validated record. Validate that
   the explanation preserves uncertainties and does not introduce facts, suppliers or amounts.
8. Company feed/watchlist consumes the result. A separate attention budget and delivery gate owns
   push eligibility; real push stays off. Optional narrative evaluation consumes company events later.

One analyst means one prompt/tool/schema role, not one permanently growing chat or one serial
process for the entire market. Independent jobs may run concurrently under queue/token limits.
A bounded two-stage extraction→retrieval→analysis workflow is a sensible initial design; avoid
an unconstrained tool loop or analyst committee on every article. Reuse extracted events across
company candidates rather than repeatedly reading the article once per ticker. Evaluation reviewers
are separate from this production role and cannot grade their own predictions.

## Input/output and authority boundaries

The experiment input pins source_id/revision/hash/as_of, source representation and completeness,
company universe, profile/graph snapshot, mechanism/ranking policy, model/prompt/schema versions,
retrieval configuration, call/token limits and runtime. Content is untrusted data, not instructions.
The analyst gets no database-write, publish or notification capability. Missing model/provider
configuration is a named unavailable arm, never a fabricated LLM result or keyword substitute.

Each output proposal should include:

- event_id and source evidence spans; family, actor/object and phase/attribution/negation;
- candidate company IDs, selected relationship IDs and support sources; scope/conditions/mitigants;
- extracted raw quantities with units, periods, numerator/denominator only when supplied;
- proposed business variable/direction with basis, separate relevance/attention/magnitude/horizon;
- missing-data/retrieval/ambiguity flags and a short explanation tied to evidence;
- validator decisions, deterministic score/tier components and complete version/provenance receipts.

A valid JSON shape or exact quote proves neither semantic correctness nor causal impact. Numerical
probabilities are not accepted solely from model confidence. The agent can recommend a database
addition in a separate review queue; it cannot turn it into a verified edge. Existing one-step,
labelled LLM-prior policy remains unchanged and cannot license multi-hop speculative chains.

Illustrative case, not market data: a source says a data-center project is delayed by a power
constraint. The analyst extracts project delay, distinguishes planned from delivered capacity,
and retrieves sourced downstream compute/server/memory demand exposure. The graph can support a
conditional sector/company context. It does not establish which supplier won that project's order,
its lost revenue or a negative stock-price outcome. Those require additional evidence.

## Scoring, weights and competitive value

Keep separate concepts: relevance evidence, conditional business mechanism, attention priority,
financial magnitude and transmission horizon. A relevant item need not have a quantified impact.
Store mechanism definitions, scope, direction on a named variable, conditions, source-backed exposure
share, inventory/contract/substitution mitigants, timing basis and data-quality status in the database.
Unknown parameters stay unknown; source-supported quantities and governed scenario estimates must
remain distinguishable in both API and cards.

Initially retain interpretable ordinal attention tiers and record features such as source novelty,
concrete development, exposure specificity and evidence quality. Predeclare any new numeric policy;
fit/calibrate weights on development data, lock them before evaluation, and test stability and group
regressions. Do not let the agent generate ad hoc weights per article or optimize on frozen test labels.
Reported score coefficients and model self-confidence are not business-impact coefficients.

The potential advantage over a generic LLM is the maintained, sourced and versioned company graph,
business mechanisms and applicability conditions, calibrated prioritization, correction-aware history
and real user feedback. Its quality and utility must be demonstrated by ablation. Public source text
plus a prompt is not by itself evidence of a durable data advantage.

## Paired comparison protocol

Preserve the current10.64company reference and25.18legacy series exactly. Use the24article reference
only for exposed development/regression. Before new evaluation, lock three arms:

| Arm | Input/processing | Purpose |
| --- | --- | --- |
| A | Current deterministic engine and same frozen database | Existing baseline |
| B | Same article and target company universe, one LLM without proprietary graph | Generic-LLM comparison |
| C | Same LLM plus scoped database retrieval, mechanism tools, validation and deterministic ranking | Hybrid candidate |

B and C use the same model/version, source representation, temporal cutoff and declared comparable
resource limits; record actual tokens/cost/latency rather than pretending retrieved context is free.
All arms see the same source facts and company universe; none sees labels or future sources. Evaluate
raw B separately from shared source/delivery safety gates. If needed, a later fixed-retrieval ablation
can isolate semantic interpretation from retrieval and scoring, rather than crediting all gain to LLM.

Freeze predictions before independent reviewers on a new cohort targeting100economic-event clusters,
with varied event families, direct/indirect paths, relevant/irrelevant controls, ambiguity, conflicting
sources and source revisions. Exclude exposed economic events as well as URLs/near duplicates. No
historical replay or fresh-source filter alone proves model pretraining independence; make no
prospective price-prediction claim. Two independent AI contexts are allowed reference construction
under existing user preference, but remain nonhuman labels with disagreements preserved.

Retain company score and per-company/group precision, recall, FP/FN/unknown. Add diagnostics for:
retrieval coverage at the declared budget; unsupported entity/edge/number claims; negation/phase errors;
explanation fidelity; p50/p95processing and end-to-end source latency; cost per100unique events; repeat
run consistency; correction/withdrawal handling and queue backlog. Count candidates not retrieved in
the denominator. Cache by source revision, graph/policy/model/prompt versions and invalidate changes.

Do not claim efficacy from a higher score alone. Require better missed-coverage/attention performance
at an explicit acceptable precision, no forbidden unsupported promotions, interpretable failure costs,
and measured latency/cost. Use paired event-cluster comparisons; company pairs within a single event
are correlated. Lock statistical/operational comparison rules before the fresh run. Existing release
targets (including precision0.85/recall0.70, sample/support and seven-day operations) are not lowered;
the new score is not a release switch. Cost/latency budgets need actual workload/model measurements.

## Authorized next implementation and unresolved choices

Prepare a separate local shadow adapter: immutable source/graph export, proposal schema, read-only
retrieval interface, validator, baseline comparison and provenance/cost receipts. Reuse source/graph
components instead of creating a second ingestion system. Complete sourced alias/exposure work in
parallel with the experiment design; a semantic reader cannot authenticate absent relationships.
No new runtime model, provider call, install, charge, upload or notification was made in this review.

A local model experiment requires an available compatible model/runtime and measured hardware limits.
An external model requires an explicit decision about provider, cost and which private text/graph
fragments may leave the machine. Ask only when that concrete execution choice is needed. Preparation
and provider-neutral contracts can proceed with LLM_MODE=none. Do not use the desktop implementation
assistant's judgments as a claimed deployed model baseline.
