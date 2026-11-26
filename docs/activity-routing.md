# Activity routing into sourced company factors

This is an experimental local extension of the compact company database, not a
stock-price model or a promoted relevance policy. Read the product direction and
development workflow before extending it.

## Contract

`FactorBinding.kind=STRUCTURED_ACTIVITY` contains a typed `ActivityRule`:

| Market | Permitted event groups | Applicability |
| --- | --- | --- |
| DATA_CENTER | FACILITY_PROJECT, PROJECT_FINANCING | Reviewed factor/path for infrastructure demand |
| AI_COMPUTE | COMPUTE_DEPLOYMENT, PROJECT_FINANCING | Conditional compute deployment or financing |
| NAMED_PRODUCT | PRODUCT_INTEGRATION, COMPUTE_DEPLOYMENT | Product name must occur in binding evidence |

Rules require explicit narrative IDs and existing sourced graph paths. Optional
vendor names must occur literally in binding evidence. The generic vocabulary in
`engine/activity_events.py` contains no issuer tickers, article titles or operator
names. The initial implementation does not resolve every participant's legal identity.
In particular, “deployed by” does not prove that the named operator made the hardware.
Only bounded explicit technology-ownership syntax supplies a vendor scope check.

Market and action must occur in the same bounded source sentence. Negation,
cancellation, rumor and conditional possibilities are withheld by this lane.
Proposed regulations are not facility projects; separate policy bindings still apply.
Source spans are preserved. Phase distinguishes seeking financing, forward-looking
plans, source-reported deployment and other reported activity. A forward-looking
plan may be editorially important without being a completed project.

The same matcher serves RSS, archive and reviewed full-article routing. Source
hashes, revisions, withdrawals, source enablement, graph eligibility, profile pins,
review expiry and feed freshness remain enforced. Old profile serialization does
not acquire an empty field, preserving existing digests. Core policy version3
recognizes typed activity as a concrete editorial signal without inventing a
direction, financial effect or lag. Weights remain unchanged.

## Local application

The candidate profiles add DELL facility/compute deployment rules and AMD named
Helios integration. A captured DELL filing paragraph explicitly links customer
data-center modernization/capacity expansion to server and networking demand;
its exact quote was added to the applicable factor relationship. NVIDIA's broad
industry activity rule becomes a typed compute rule, and the legacy generic
compute-access rule is narrowed to same-sentence shortages/constraints.
Shared power, land, financing and permitting paths remain separate.

This narrowing has measured recall costs. It is not activated as the default
registry. The opt-in workspace is
`source-cache/activity-workspace-2026-11-26.json`; detailed sources, profiles,
labels, SQLite, captures and visual checks remain ignored under
`source-cache/activity-routing-2026-11-26`. Its `atlas-v2`/`registry-v2` preserve
76nodes,83relations,39exposure facts,13financial sets,4financial bindings and
8entity references; financial cells were rechecked against unchanged source bytes.
Prior snapshots and frozen prediction files remain intact.

## Evaluation and limitations

See [aggregate report](../reports/activity-routing-regression.json). Latest
24RSS articles/216pairs and3complete-body articles/30pairs were already reviewed
by two independent AI contexts. All results here are **exposed development
regressions**, not a new blind holdout, prospective backtest or human gold.
The older RSS comparison has1716pairs/308lexical clusters. Cohorts overlap in
economic themes and are reported separately, not pooled as independent samples.

The candidate recovers concrete project/deployment and named-product events in
the latest samples, while losing previously labeled NVIDIA relevance in the
older RSS cohort. Some losses are explanatory themes or other vendors' products;
others involve named-company infrastructure. Existing labels are preserved.
Improved results on the latest sample do not justify suppressing the older loss.

Next priority is a database-backed distinction between shared industry context,
customer demand, direct product activity and explicit competitor mechanisms.
Use scoped product/vendor references and separate context-versus-priority output,
then run all exposed regressions before freezing a new unseen grouped cohort.
Do not recover recall by adding per-title exceptions or by silently relabeling
inconvenient examples. MU/SNDK positive coverage and broader group support remain
insufficient. Magnitude/horizon and commodity gates are unchanged and uncalibrated.
Real notifications remain disabled; there is no cloud deployment.
