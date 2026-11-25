# Commodity price → company input relevance

Implemented 2026-11-25 as a local workbench, not live feed/map delivery. User decision supersedes the legal-entity prerequisite for this separate commodity lane. Strict legacy R05 remains unchanged for other paths.

## Data and rules

`engine/commodity_context.py` matches a reviewed commodity observation to reviewed, version-pinned input bindings in the atlas. A binding names an actual input and an eligible, sourced `USES_INPUT` or `DEPENDS_ON` edge from a product, segment or facility. No legal entity anchor or company mention in the news is required. One commodity can route to multiple company inventories. No industry-wide fanout without input evidence, fuzzy name matching, or fabricated decomposition of generic input labels.

`config/commodity-alert-policy.json` is versioned: absolute change **>5%** creates a candidate, **>=10%** marks STRONG_PRICE_MOVE. Exactly 5% is suppressed; increases and decreases are symmetrical. These experimental thresholds measure price movement, not company financial impact. Default freshness is at most 7 days since explicit period end, or publication for supported relative periods; this is a configurable engineering choice, not an empirically calibrated rule.

Observations carry exact quote offsets and reviewer identity/kind. PRICE_PAIR requires previous/current prices, explicit same currency and unit, and start/end ISO dates in the quote. Formula `(current-previous)/previous*100`; no conversion, missing denominator or invented prices. REPORTED_CHANGE uses the source's percent and direction, with dates or a supported explicit phrase such as “over the past week”. Relative phrases remain literal with null endpoints; publication is a freshness reference only. Ambiguous, negated, forecast, percentage-point or approximate statements are held for review. Reviewer annotations declare semantic comparability; exact spans alone do not prove it.

Source packet/review chronology, CURRENT epoch, atlas hash and binding expiry are checked. Bindings expire within 90 days. With `--news-current`, current registry revision and polling freshness are enforced; an existing registry binding cannot be silently omitted. Withdrawal or a source change during evaluation removes candidates. Manual source ledgers are explicitly local research only. Polling does not prove full publisher-page freshness.

## Output and non-fabrication

Candidate cards expose source quote/URL/epoch, measurement/formula, input relationship/evidence, company/product, directly watched narratives, policy/binding hashes and conditional cost pressure. Financial magnitude/horizon stay UNKNOWN; probability and price prediction are null. Applicability of benchmark grade/geography is UNVERIFIED. Check cost share, inventory, hedging, contract reset, pass-through and substitutes before asserting company impact. A 12% input price rise is not a 12% profit decline.

No data may be invented: distinguish supplied facts, reproducible calculations, database-backed conditional inference and unknowns. Detailed source data remains local. Notifications and synthetic live delivery stay off.

## Command

```powershell
python -m engine.mechanism_playbook commodity --atlas <snapshot-directory> --input <observation.json> --selection <selection.json> --articles <article-root> --scope-store <review.sqlite> --commodity-bindings <bindings.json> --output <local-output.json>
```

Optional `--commodity-policy <versioned-policy.json>` and `--news-current` (configured database). Bindings file is a JSON list of `InputBinding`; input is `Observation`. See models and tests for exact fields.

## Limits and next acceptance gate

Current tests use synthetic prices/companies, not independent labels. No new real commodity facts or measured accuracy improvement are claimed. Existing generic input nodes need sourced, commodity-specific bindings; aliases/grade/geography are not automated. Relative-period vocabulary is bounded and conservative wording checks can hold valid news. Direct narrative watches only; no multi-hop narrative expansion. No cross-run bundling/dedup or active feed integration yet.

Next: populate a small real input registry with benchmark applicability, evaluate new positive/negative commodity news groups without article-specific patches, then integrate candidate cards into the private feed with correction/retraction and dedup. Measure missed/incorrect relevance separately from unverified financial magnitude.
