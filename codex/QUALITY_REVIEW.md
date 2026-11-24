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
