# Sourced operating readiness context

`readiness-context-v1` links resource conditions to an explicitly reviewed company
factor and narrative. It is shared by RSS and full-article routing. It adds no
ticker, headline or company-specific branch and does not change numeric weights.

The optional `FactorBinding.readiness_context` declares:

| Field | Contract |
| --- | --- |
| `scope` | `CUSTOMER_DEPLOYMENT` or `MANUFACTURING` |
| `resources` | Bounded selection of `POWER`, `WATER`, `CONSTRUCTION` |
| `relationship_id` | Existing outgoing mechanism from the binding's factor |

Both binding and mechanism evidence must quote the declared resource and operating
market. Customer deployment requires `AFFECTS_DEMAND` and DEMAND/DEPLOYMENT intent;
manufacturing requires `AFFECTS_SUPPLY` and SUPPLY intent. The exact mechanism must
occur on the eligible route. Competition cannot donate a route. Existing source,
version, correction, withdrawal, time and maximum-hop checks remain authoritative.
Overlapping matcher guards, unsupported resources and dangling mechanisms are rejected.

The matcher requires a resource-condition phrase and operating market in one source
sentence, within 220 characters without a coordination/clause boundary. Examples
include power availability, grid strain, shortages of electrical power, stranded
data-center power and paused construction. Low-power memory capacity and component
power efficiency alone do not establish utility availability. Manufacturing accepts
explicit semiconductor/chip/memory production or general explanatory industrial
utility context; unrelated factory sectors are withheld. Original field offsets and
the resource/scope/mechanism trace accompany every match. It cannot borrow a market
from the title for an unrelated sentence in the excerpt.

All matches from this contract are `context_only`. They do not independently promote
a card into editorial priority, even when the source describes a concrete incident.
Another independently qualified binding may still support priority. Company incident,
customer/vendor identity, financial direction, magnitude and horizon remain unknown.
This version does not claim geographic facility exposure, fulfilled orders or verified
causal impact. Generic utility explainers can remain in background/sponsored research.

The local rollout adds AMD customer-buildout exposure/demand and MU manufacturing
utility exposure/supply paths from already-cached primary filings, then two opt-in
bindings. Source bytes, narrative targets and labels are unchanged. DELL receives no
new power/construction edge because its cached filing does not substantiate one.
NVIDIA customer-demand evidence is not converted to a supply mechanism.

See [evaluation](../reports/deployment-readiness-review.md) and the local checkpoint
for immutable per-step runs. This is an exposed AI regression improvement, not fresh
blind validation, human gold, financial-impact calibration or release acceptance.
