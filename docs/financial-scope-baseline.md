# Financial scope map and evaluation baseline

Use atlas `--bindings LOCAL_BINDINGS_JSON` in addition to the reviewed financial
selection input. A FinancialBinding declares a current profile product/segment node,
financial dataset and part cell, SUBSET_OF_BUCKET or CONTAINS_BUCKET, scope and
reviewer/time/exact source evidence. No automatic name matching, equality claim,
share allocation or causal approval occurs. Source quote matching verifies provenance,
not the interpretation; operator AI reviews remain separate from independent labels.

The local map offers a Financial view with reported revenue buckets and reviewed
scope links. The reporting layer remains separate from the base graph and is excluded
from Scenario traversal. A reporting bucket's company revenue share never becomes
its linked product's affected revenue share. Corporate reconciliation is not a product.
Separate partitions (segments/products/end markets) must not be added together.

Current scope:22reporting buckets in five companies; four reviewed links in DELL,
NVIDIA and MU. AMD process-node groups do not match business segments and remain
unbound; Sandisk linkage needs its own scope review. These gaps are explicit.

## Freeze and verify locally

```
python -m engine.atlas_freeze create --atlas LOCAL_ATLAS --criteria config/impact-group-acceptance.json --output source-cache/NEW_BASELINE
python -m engine.atlas_freeze verify --output source-cache/NEW_BASELINE --expected-sha256 SEPARATELY_RECORDED_BASELINE_HASH
```

Creation copies the atlas and predeclared criteria into a new directory and fingerprints
engine/web code, config JSON and declared dependency manifests. Verification requires
the separately recorded receipt hash and rejects artifact or current code/config drift.
Never overwrite or repair an old baseline; create a new version and preserve history.
This is not a package/OS/VM capture, cryptographic reviewer attestation or current
publisher/source-revocation check. Keep detailed artifacts and baseline local.

This baseline contains zero event clusters and no locked predictions or labels.
Next: collect disjoint economic-event clusters, explicitly assign a family and split,
lock predictions against the pinned baseline, then independently label. Preserve
relevance, scope, causal channel, horizon and strength as distinct assessments.
Source availability at the event time still needs its own review: this current atlas
must not be presented as a historically point-in-time valid backtest automatically.
Existing seven-family targets remain predeclared/unvalidated; weights and delivery
stay disabled. A frozen database alone is not algorithm acceptance.
