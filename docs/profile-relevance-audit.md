# Multi-company supply profiles and relevance audit

Local profiles now cover NVDA, AMD and MU (four bundles including the existing historical NVDA example). AMD source-backed supplier nodes distinguish TSMC CPU/GPU wafers at <=7nm and GlobalFoundries primarily >7nm. These are scoped supplier assertions, not whole-company capacity dependencies. MU covers manufacturing materials and strategic-customer cohorts; source passages do not identify the counterparties, so no names are inferred. NVDA's customer affiliate of OpenAI is not resolved to OpenAI's parent identity. No relationship is promoted into the global verified graph.

NVDA supply v2 also corrects a review error in v1: several evidence selections matched a table row beginning with “Supply and capacity” instead of the explanatory paragraph. The old immutable version remains; the current version cites the actual explanatory text. Hash and quote-presence checks alone cannot validate semantic support. The remaining source-backed fields are AI-curated assertions requiring review before higher-trust use.

The new local evaluation CLI freezes current article/narrative pairs and predictions separately:

```powershell
$env:DEV_INFORMATIONAL_FEED='true'
$env:DATABASE_URL='sqlite:///rie-dev-feed.db'
python -m engine.evaluation.profile_relevance freeze --directory source-cache/my-relevance-audit --count 100
python -m engine.evaluation.profile_relevance evaluate --directory source-cache/my-relevance-audit --labels source-cache/my-relevance-audit/labels.json
```

Never reuse an existing output directory. Freeze stops on invalid/truncated profiles or a truncated inbox. Valid same-URL copies count once; conflicting current content is excluded. Packet includes article payload, profile identity/version/hash, scoped narrative, source evidence and relationships, without predictions or term rules. Predictions live in a separate file. File separation is not access-control isolation. Keep the entire directory private; only aggregate counts should be committed.

Labels contain packet_sha256, reference_kind (AI_DEVELOPMENT_REVIEW or HUMAN_REVIEW), and exactly one id/relevance/rationale per pair. Relevance is RELEVANT, NOT_RELEVANT, or INSUFFICIENT_CONTEXT. Hash mismatch, missing/duplicate labels, missing rationale or unrecognized provenance is rejected. Unknown references are excluded from precision/recall rather than counted as negatives. Current routing may include expiry and source-availability gates; reported recall measures the complete feed selection, not just term matching.

## Development result, 2026-11-22

The first 60 recent URL clusters yielded 240 pairs, mostly administrative/off-topic, with no positive references: precision/recall undefined, not 100%. That freeze was retained. Expanded the convenience sample to 100 clusters/400 pairs, with no rule tuning, to inspect a wider inbox window. Same implementing AI read titles/excerpts and assigned development references before opening prediction scores; this is not an independent blind review or a holdout benchmark. Near-duplicate stories on different URLs are not yet grouped; article/narrative pairs are correlated.

Expanded sample: TP1, FP0, TN375, FN4, unresolved20. Five reference positives; one selected card. Recall20%; numeric precision1/1 is too sparse to support a quality claim. Misses concern financing, permitting, building restrictions and AI-model compute access: broader narrative relevance than the current construction/power keyword conjunction. No truth verification or price-impact labels were supplied. Scores do not measure whether the news itself is correct.

The sample contains no adequate positive examples for the new AMD supplier and MU materials rules. Their live relevance accuracy remains unestablished. Synthetic tests establish software invariants only. Do not tune on this exposed set and report improvements as held-out accuracy. Next: construct reviewed mechanism-specific policy/finance/compute factors, add supplier/customer alias disambiguation and site/product scope, then freeze a fresh stratified dataset with independent references and cross-URL event grouping. Notifications remain disabled; there is no launch or live push approval.
