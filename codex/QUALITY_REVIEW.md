# Quality review after each iteration

Standing user request: after every iteration, identify current system limitations,
feasible remedies and the evidence needed to verify improvement. Read this alongside
CHECKPOINT.md. Do not treat passing software tests as market accuracy or product acceptance.

Each handoff must include: what changed; measured outcome with denominators; unresolved
limitations; ranked next remedies; validation gate for each proposed remedy; data and
notification state. Keep detailed news, labels and predictions local. Preserve prior
baselines and never recycle an exposed diagnostic set as a fresh holdout.

## 2026-11-24: identity-grounded scope population

| Priority | Limitation and evidence | Feasible remedy | Required verification |
| --- | --- | --- | --- |
| P0 | Narrow regex extractor produced0events across23exposed real articles;1571clauses unsupported. This is coverage diagnosis, not a new blind accuracy score. | Replace the sole regex gateway with a pluggable structured extractor: evaluate an offline dependency parser or a separately approved candidate model. Require source spans and independent semantic review; keep regex as a baseline. Do not add article-specific phrases to chase this set. | Fresh disjoint articles; score actor/action/object/negation/phase extraction separately, including unsupported rate and false claims. |
| P0 | Ten rules cover only AMD foundry resilience, two suppliers; four companies remain unpopulated. | Build a reviewed product/factor taxonomy and scoped aliases from issuer evidence; separate broad industry context from exact company exposure. Populate only where identities and directed paths are supported. | Per-company and per-mechanism positive/negative coverage on a new blind cohort; no unsupported relation created to reach a quota. |
| P1 | Exact surface scopes lose paraphrases and generic supplier-outage news lacking process/product detail. | Add product-scope subsumption with explicit subset/unknown states; missing process/geography must remain conditional context, never verified exposure. | Near-miss product/node/geography negatives and independent scope labels. |
| P1 | Same quote can mention several entities; name occurrence alone previously permitted wrong actor-to-edge attribution. | Implemented identity_reference_id authorization tied to upstream node and cited incident relationship; strict mode rejects legacy name-only rules. |11scope regressions pass, including same quote/wrong supplier. Real-world false-positive change remains unmeasured. |
| P1 | Rule/source interpretations are AI_OPERATOR declarations; agreement is not human truth. | Two separate-context AI reviews for new samples, disagreements retained; seek human review before production acceptance. | Report reviewer provenance, disagreements and unresolved references; never silently convert unknowns to negatives. |
| P1 | Phase, duration and financial strength remain uncalibrated. | Separate proposed/committed/operating assertions; add source-bound timing/quantity fields and conditional transmission analysis. | Verified units, periods, affected scope and causal-group labels; company segment share is not an impact weight. |
| P2 | New shadow rules do not affect the live feed. | Integrate only after extraction/scope gates pass; retain review queue and source correction/withdrawal checks. | End-to-end feed freshness, source lifecycle and user relevance acceptance; notifications remain disabled. |

Decision: identity safety and reusable scope readiness improved; real-news recognition
has NOT been shown to improve. The next engineering priority is general extraction and
scope representation, not calibrating weights or broadening keywords one story at a time.

No need for a user decision to continue local parser/contract experiments. A paid/external
model service, new data transfer or live notification activation would require a concrete
proposal within the user's authorization. No such service was enabled in this iteration.

### Concrete extractor experiment to prepare next

The current virtualenv has no spaCy, Stanza, transformers, torch or onnxruntime.
An isolated spaCy English pipeline is a feasible local candidate for dependency
relations and noun chunks; these are syntactic proposals, not financial semantics.
Pin both package and trained-model versions/checksums before a new comparison.
Use source span validation and a common event schema so the extractor can be replaced.
Do not assume pretrained entity recognition resolves semiconductor products or legal
subsidiaries. No model/package was installed and no private article was sent to an API.

Primary references checked2026-11-24:
[spaCy linguistic features](https://spacy.io/usage/linguistic-features) and
[trained pipeline installation/versioning](https://spacy.io/usage/models).
The proposal is an engineering hypothesis to test, not an accuracy claim.

Diagnostic counting note: the1571unsupported units are parser fragments, including
non-event prose and financial table cells. They are not1571missed economic events.
No supported-event recall denominator was independently labelled in this iteration;
the defensible observation is zero extracted candidates across23exposed documents.

## 2026-11-24: local dependency proposals and scope algebra

Measured:23exposed documents ->345syntax proposals,296flagged;95focused tests and8actual-model synthetic cases passed. This improves reviewable extraction coverage, not proven accuracy. No canonical events/cards, no new blind evaluation.

| Priority | Current limitation | Feasible remedy | Verification gate |
| --- | --- | --- | --- |
| P0 | Syntax proposals include metrics/descriptions, not necessarily economic events; zero precision/recall labels. | Independent source-first assertion labels on50–100new disjoint clusters, then general event/mechanism normalization. | Freeze before labels; report candidate precision and source-assertion recall separately by group. |
| P0 |296/345proposals flagged;91include pronoun actors; explicit subject inheritance/coreference unsupported. Common noun references also remain unresolved even without a pronoun flag. | Add separately evaluated reference/attribution resolution; preserve ambiguity and source span chains. | Cross-company, quoted speaker, passive/negation/conditional and multi-clause adversarial cases; no wrong affirmative promotion. |
| P1 | Sentence-wide flags over-hold unrelated clauses; phase mostly UNKNOWN and time/quantity only raw tokens. | Evaluate clause-scoped cues plus explicit temporal/unit normalization; never infer committed/operating from a plan. | Independently labelled phase/negation matrices and unit/period checks. |
| P1 | Two scope annotations/one company; no automatic source-backed synonym/subset taxonomy. | Populate versioned reviewer vocabulary and product/facility scopes from sources across remaining companies. | Independent scope labels; broad wafer news stays UNKNOWN when process/geography missing. |
| P1 | Exported queue is a snapshot and does not follow source corrections. | Revalidate packet/profile/source status at future review acceptance and integration; invalidate stale decisions. | Correction/withdrawal/review-expiry end-to-end tests before cards. |
| P2 | Model uses generic English training and optional environment; no domain benchmark. | Keep pluggable proposal contract, pin versions and capture complete runtime/model fingerprints; compare alternatives on the same frozen source-first labels. | Dedicated actual-model CI smoke plus blind benchmark; package audit excludes model not indexed on PyPI. |

Next decision: validate semantics on unseen source-first labels before increasing output volume, tuning weights or routing proposals into feed. All new scope comparisons explicitly deny impact authorization. The protocol is documented; actual fresh collection/reviewer execution remains pending.
