# Local atlas financial context

The atlas now accepts `--financials LOCAL_SELECTIONS_JSON` alongside existing
`--profiles`, `--facts`, `--identities` and `--output`. Use a new ignored output
directory for every build. Source documents, selections, detailed financial values,
database, map and screenshots stay local; publish only code/tests and aggregate progress.

Each FinancialSelection declares profile/source IDs, CIK, version, reviewer/time,
scope, classification and pinned total/part/prior fact IDs with context IDs and
expected dimensions. No numbers are typed into the selection. The builder derives
them from the original hash-verified filing, preserving reported text, scale,
decimals, concept, period and source identity. Review time must follow both source
capture and selected profile availability. `AI_OPERATOR` is not human validation.

Supported classifications:

- REPORTABLE_SEGMENTS: business-segment axis, optional operating-segment consolidation
  marker, and explicit corporate/non-segment reconciliation. No product subgroups.
- PRODUCTS / END_MARKETS: separate reviewed product-or-service-axis partitions.
  They must never be summed with the segment partition or each other.
- INVENTORY_BALANCE: two ordered consolidated InventoryNet instants in USD.
  No inventory buffer, days, physical units or outage coverage are inferred.

Revenue operands must share source, issuer, concept, currency and exact duration.
A positive consolidated denominator and nonnegative parts must reconcile exactly.
Missing residuals, rounding differences, mixed axes, nested subtotals and duplicate
members are rejected; do not add a fabricated balancing row. Reported precision is
preserved; the derived ratio does not acquire greater economic certainty. This
release does not support negative reconciliation items or arbitrary XBRL taxonomies.
Only explicit supported numeric transformations/plain USD units are accepted.
Unsafe XML, duplicate IDs, hidden facts, typed dimensions, namespace rebinding,
future periods and unsupported formats fail closed.

The financial-context UI displays every partition separately, with an inventory
comparison and a source-cell detail action. The SQLite payload keeps source/profile
foreign keys. Previous snapshots remain readable. Snapshot verification checks
integrity, not live source availability or subsequent restatements; rebuild after
profile/source review. This is a research inspector, not the active news feed.

Current aggregate:13datasets (8revenue partitions and5inventory pairs) across five
companies,40selected source cells and22partition parts. Reporting periods differ
between companies; annual Micron data must not be treated as a quarter. The local
review-report.md lists the exact periods, values and source URLs. Do not upload it.

Four qualitative additions document manufacturer-switch constraints and pricing
terms. Fixed/variable/banded pricing and management pricing intentions do not imply
a contractual input-cost pass-through coefficient. Accounting inventory balances
are not physical buffers. These uncertainties remain outside calibrated scoring;
all impact weights and inferred buffer days remain null, delivery disabled.
