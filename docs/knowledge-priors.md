# One-step LLM knowledge in the relationship database

User decision, 2026-11-25: fill missing knowledge with clear, widely known LLM reasoning, at most one inference step. Do not estimate obscure or ambiguous information. This refines the earlier no-fabrication rule: estimates are allowed when labeled; invented news facts or misrepresented disclosures are not.

## Implemented contract

`engine.knowledge_priors` creates a local SQLite/JSON knowledge database pinned to an immutable atlas. It is a companion layer, queried with `lookup`, rather than an overwrite of source-reported exposure facts. Source-reported/non-UNKNOWN fields win, including disputed/not-applicable states. New versions use new directories and hash manifests; `read` verifies artifacts. No API calls, automatic external LLM inference, cloud delivery, active feed or map change.

The maintained `config/knowledge-priors.json` is LLM-authored general knowledge with explicit applicability and exceptions. It currently has three qualitative rules:

| Source premise | One-step prior | What remains unknown |
|---|---|---|
| Product USES_INPUT | Possible purchase-cost pressure if actual terms change | Input share, margins, horizon |
| Activity DEPENDS_ON factor | Possible constraint in that documented scope | Dependence strength, alternatives, timing |
| Company COMPETES_WITH peer | Possible customer substitution where products overlap and switching is feasible | Realized market-share/sales gain, net direction |

Only active SOURCE_BACKED + SOURCE_REPORTED relationships with source evidence qualify. CANDIDATE, CONDITIONAL_MECHANISM, ISSUER_ATTRIBUTION and prior-derived premises do not. The output retains source quotes as **premise evidence**, not citations proving the LLM conclusion. No cross-company identity merging or second inference occurs. Existing dimensions are filled only if UNKNOWN; rule collisions fail rather than using last-write-wins.

Each prior has LLM_PRIOR_UNVERIFIED, rule/version/hash, premise hash, scope, author, knowledge time, 90-day review expiry, conditions and exceptions. Lookup checks the atlas pin, expiry and exact reproducibility from original premises. Atlas changes require rebuilding; old priors are not silently carried forward. Existing source facts keep their own lifecycle contract. Snapshot integrity is not proof that a publisher has not withdrawn an article since capture.

## Numeric estimates

The rule schema supports fraction/day intervals with a denominator and explicit estimation method. Finite, ordered, nondegenerate bounds are required; fractions must lie in [0,1]. It never converts qualitative wording into a point estimate. A typical material composition must not be applied as a cost share; a product cost share must not be applied as a company-wide profit effect.

No real numeric priors are seeded in this version: the current mixed semiconductor/system profiles do not supply a sufficiently unambiguous general recipe for those percentages. Numeric tests are synthetic contract checks only. Future numeric rules require a genuinely common, clear reference class and explicit applicability; configuration validation cannot establish that an LLM recollection is true. When uncertain, obtain a source or leave UNKNOWN. Do not use a wide arbitrary range as a substitute for a basis.

## Local use

```powershell
python -m engine.knowledge_priors --atlas source-cache/ATLAS --author "LLM operator identity" --output source-cache/NEW_PRIOR_VERSION
```

Optional `--rules` selects a maintained versioned catalog. Use `read(output)` then `lookup(bundle, current_atlas, relation_id, dimension)`. Lookup returns ATLAS, LLM_PRIOR_UNVERIFIED, or UNKNOWN. Conditional relevance/scenarios may consume the labeled result; no promotion to verified impact or source-backed commodity bindings. Any further inference from the prior is forbidden. Keep actual observations separate when testing scenarios.

## Review and next work

The initial local population is a database enrichment, not proof of improved ranking. Commonness and clarity are author judgments, explicitly unverified. Assess new grouped events with/without priors, track false relevance and source contradictions, and replace/rebuild priors when evidence arrives. Prioritize supported material recipes and scoped dependence/competition coverage; avoid filling every blank. Integrate clearly labeled priors into feed/map only with source lifecycle and provenance preserved. Notifications remain disabled.
