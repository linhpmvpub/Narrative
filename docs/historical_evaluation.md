# P5 offline historical evaluation workflow

This tooling validates an explicitly supplied corpus and compares submitted V0 results with a deterministic B0 keyword baseline. It does not acquire sources, label events, run an LLM, enable notifications, or establish that a claimed archive is genuine. Real historical evaluation is pending. The checked-in `evaluation/historical-v0/` workspace is empty and contains JSON schemas, not fabricated examples.

## Collection and review

Collect 50–100 distinct canonical events across MU, NVDA, AMD, DELL and SNDK from approved sources. Target at least 30% negative/irrelevant/reprint examples and 20 distinct relevant two-hop events. Every event/narrative-version pair is a separate `Case` line in `cases.jsonl`; event and pair denominators are reported separately. Include difficult negatives and corrections. Use the same canonical key for reprints/corrections. Never map WDC HDD history to post-spin SNDK.

Each case requires a stable ID, canonical event/version, narrative version, ticker, factual headline, explicit synthetic flag and aware `as_of`; source URL, document SHA256, archive ID, reviewed rights approval and publication/first-seen/availability/retrieval clocks; narrative, edge and metric availability clocks. Store source archives and actual policy traces separately and retain access controls. An approved-rights field is an operator assertion, not automated license verification.

All input clocks must be at or before the case cutoff. Availability cannot precede publication/first sighting. These checks intentionally follow the existing engine's strict cache-only replay rule: a document first retrieved today cannot be backdated merely because it describes last year's results. Genuine historical capture evidence or a separately reviewed archive-adapter design is needed. A later human gold-label review is allowed because labels are evaluation targets, never model inputs. Real-mode records reject common fixture URL domains; this is a basic guard, not authenticity verification.

Choose explicit chronological boundaries in `split.json`: `development_end`, `calibration_end`, `holdout_end`, each an increasing timezone-aware ISO timestamp. Boundaries are inclusive at the end of each partition. Cases beyond the corpus end are rejected. A canonical event, event version, or identical source document cannot cross partitions; move boundaries or group cases deliberately rather than silently dropping difficult examples. Narrative versions may recur legitimately, but their availability must precede each cutoff.

## Commands

From the project directory, with the virtual environment active:

```powershell
# Only when creating another new workspace; the supplied one already exists.
python -m engine.evaluation.cli init evaluation/another-corpus

# After collecting cases and choosing chronological boundaries:
python -m engine.evaluation.cli freeze --cases evaluation/historical-v0/cases.jsonl --split evaluation/historical-v0/split.json --output evaluation/historical-v0/manifest.json
python -m engine.evaluation.cli label-template --cases evaluation/historical-v0/cases.jsonl --output evaluation/historical-v0/labels.jsonl

# After independent human review and export of actual V0 predictions:
python -m engine.evaluation.cli evaluate --cases evaluation/historical-v0/cases.jsonl --labels evaluation/historical-v0/labels.jsonl --predictions evaluation/historical-v0/predictions.json --manifest evaluation/historical-v0/manifest.json --output reports/historical-evaluation-v1.json
```

The empty supplied corpus cannot be frozen. Schema files document required fields. Generated label templates contain null placeholders and deliberately fail validation until a reviewer completes them. Labels require reviewer/time, novelty, relevance, materiality, path validity/hops, stance, push/digest intent, negative/reprint classification, reason and citations from the frozen case. Do not derive gold labels from V0 predictions or original synthetic expected outcomes.

Prediction input is a JSON envelope with `dataset_sha256` matching the frozen manifest and `items` conforming to `prediction.schema.json`. Each item includes `case_id`, `matched`, `decision`, `policy_version`, `trace_sha256`, and optional measured `latency_ms`/`cost_usd`. Export these from the actual policy runner and archive the trace whose hash is recorded. This tool checks coverage and schema; it does not independently recompute or authenticate submitted trace hashes. No real source-to-policy exporter is claimed here.

The manifest hashes sorted case content and split boundaries. Evaluation refuses changed manifests, duplicate pairs/IDs, missing or extra labels/predictions, unrelated label citations, mixed synthetic/real corpora or mixed policy versions. CLI output uses exclusive file creation: existing manifests, labels and reports are never overwritten. Preserve manifests in reviewed version control or immutable storage **before tuning**; a local hash alone cannot prove when freezing happened. A revised corpus needs a new reviewed manifest and a fresh untouched holdout.

## Interpretation

- B0: ticker word in headline and source recency <=30 days. Reports relevance matching; its push metric is null because keyword matching is not a delivery policy.
- B1: UNAVAILABLE, `LLM_MODE=none`.
- V0: submitted policy results, evaluated on exactly the same cases. Reports relevance and push confusion counts, material-pair match recall, valid two-hop match recall, partition and ticker breakdowns, and disagreements for review.
- Ratios include numerator/denominator and descriptive Wilson 95% intervals. A zero denominator produces null, never a perfect score. Multiple narrative pairs for one event are correlated; these intervals are not independent event-level confidence claims.
- Latency reports observed/expected counts and nearest-rank p95 for observed timings. Cost total remains null unless every prediction supplies measured cost. Missing measurements are never treated as zero.
- Actual duplicate deliveries, factual error rate, time to review, weekly false-alert rates and user feedback effectiveness need additional independently collected records and remain unavailable. Pair-level false-positive counts are not weekly delivered-alert rates.

Corpus composition checks are visible even for small development datasets; failure does not silently discard records. Evaluation always returns NO_GO: an offline score cannot attest source authenticity, holdout isolation before tuning, production security, PostgreSQL runtime behavior or Threadnote integration. Release review remains a separate P5 task. Synthetic test metrics are never presented as real historical performance.
