# Memory company coverage challenge — 2026-11-27

This development evaluation targets previously weak MU/SNDK coverage. It uses
current sourced profiles on complete archived issuer releases, not prospective
news delivery, historical as-of knowledge or a random market sample. Financial
impact strength, lag and stock returns are not evaluation targets.

## Collection and novelty

The local plan requested16articles,8per issuer, before predictions or labels.
Bounded discovery captured25candidate releases. Selection prioritizes product,
input-material, manufacturing, supply, demand and finance developments while retaining
routine investor/governance notices as scope controls. Fifteen were selected:
8Micron and7Sandisk; the Sandisk quota shortfall is preserved. No claim that the
selected stories are relevant is made before independent review.

The main Micron IR index and one linked release returned403; failures are retained.
The public Micron archive on `micron.gcs-web.com` and Sandisk corporate release pages
are readable. Those exact hosts are now allowed for explicit local article capture.
No arbitrary subdomain, redirect following, authentication bypass, new live source
configuration or automatic fact approval is introduced. Synthetic tests check local
capture/read integrity, unreviewed status and rejection of lookalike hosts.

The novelty audit verifies27unique prior frozen packet hashes and compares595unique
article representations, canonical URLs, text overlap and existing profile source URLs.
One additional Sandisk manufacturing release is conservatively excluded because of
its proximity to a previously exposed BiCS10 announcement. Different URLs alone do
not establish an unused event. Source boundaries are reviewed from the lead/subtitle
through qualifications, About, cautions and contacts, excluding menus, duplicated
headings and shopping/footer content. Full source text remains preserved; the existing
matcher separately suppresses boilerplate.

Publication instants come from original `datePublished` or `article:published_time`
metadata with explicit offsets. One excluded candidate's URL contains a different date from
its displayed/metadata date; URL dates are not treated as publication evidence.
Content is recaptured and compared exactly before prediction freeze. Source claims
remain issuer claims, not independently verified outcomes.

Unseen means not matched to the audited project evaluation/source exposures. It does
not mean unknown to model pretraining or wholly unrelated to any previously discussed
company project. Investment phases in an existing JV and repeated investor-event
templates can remain dependent. Lexical clusters and reviewer flags are reported
without claiming verified economic independence. Earnings periods are excluded.

## Freeze and review

The existing complete-body and dual-priority workflows lock15article clusters /
150article–narrative pairs across6profiles and10narratives. Predictions are frozen
before two reviewers receive the prediction-free compact packet. Matching rules,
scores, predictions and peer labels are withheld from both separate AI contexts.
The packet retains source text, sourced company relationships and narrative scopes.
Independence is declared context separation, not filesystem isolation or human gold.

Relevance and editorial priority are labeled separately, along with actual event
groups. Group labels may overlap. Disagreements remain unresolved; the implementation
agent does not adjudicate labels to fit predictions. The matcher/database/weights are
unchanged for this challenge, so results diagnose coverage rather than demonstrate
an algorithm improvement. No automatic promotion or notification activation follows.

Detailed captures, plan, novelty audit, complete-body boundaries, prediction freezes,
review-only packets, reviews and diagnostics stay under ignored
`source-cache/memory-unseen-2026-11-27`. Existing runtime/atlas snapshots are retained.
Run the evaluator with `NEWS_ARTICLE_DIR` set to that directory's `articles`,
`DEV_INFORMATIONAL_FEED=true`, `SEND_NOTIFICATIONS=false`,
`ALLOW_SYNTHETIC_LIVE=false` and `LLM_MODE=none`. Do not rerun freeze into an existing
directory or overwrite the locked predictions. Results are recorded in
`reports/memory-unseen-evaluation.json` and the checkpoint.

The selected publication range is2025-08-05 through2026-11-12. Collection and review
occur on2026-11-27. These dates must not be conflated or used to backdate knowledge.

## Results and decision

Both separate AI reviewers completed150pairs after prediction freeze. Five relevance
disagreements and11priority disagreements remain unresolved. Event-group assignments
agree; counts overlap where one article has several groups. One related Micron
investment family was flagged by both reviewers: merging it for a descriptive
sensitivity check reduces15lexical clusters to14family components. Original frozen
clusters, labels and predictions remain intact.

| Routing against relevance reference | TP | FP | FN | Unresolved | Recall |
|---|---:|---:|---:|---:|---:|
| All150pairs |13|3|25|5|34.2%|
| MU15pairs |0|0|10|0|0%|
| SNDK30pairs |4|0|4|0|50%|
| AMD30pairs |0|1|3|1|0%|
| NVDA45pairs |4|1|5|2|44.4%|
| DELL30pairs |5|1|3|2|62.5%|

Overall precision is81.25%(13/16resolved selected pairs); one selected pair is
unresolved and excluded from that denominator. Routing and the locked broader
candidate coincide here. Main-priority selection finds4relevant pairs with1false
positive and34misses; against the separate priority reference it finds4priority
pairs with1false positive and28misses. Broad routing includes12priority positives
with3false positives and20misses, plus2selected unresolved priority pairs. These
references do not authorize changing main-card visibility or push delivery.

| Actual event group | Article clusters | Routing TP/FP/FN |
|---|---:|---:|
| Technology |5|8/1/13|
| Capacity |3|5/0/9|
| Demand |3|2/2/7|
| Financing |4|3/2/7|
| Other controls |4|0/0/0|

No input-price, policy or supply-disruption events were resolved in this cohort.
Source availability and curated selection do not establish comprehensive market
coverage. MU now has10resolved positive lexical clusters, but9under the related-family
sensitivity; SNDK has6. Per-company support and release gates remain unmet. This
cohort becomes exposed development data after diagnosis, not a reusable fresh holdout.

## Systematic diagnosis and next work

MU has sourced manufacturing, customer-contract and competitor information, but only
two bindings: narrow input-material conjunctions and first-person supplier-role
disclosure. Six missed own-company developments and four missed competitor-context
pairs reveal a missing connection from existing database knowledge to news routing.
More graph nodes alone would not fix that gap. SNDK misses consumer release wording,
external automotive/data-center flash demand agreements, and an investment article
judged relevant demand context; the last case has unresolved editorial priority.

The three false-positive classes are general venture capital treated as concrete
infrastructure financing, vehicle-qualified memory supply treated as server inputs,
and a bilateral component agreement treated as a named rack deployment constraint.
Some misses are component-readiness context rather than increased infrastructure
demand. Preserve that distinction in cards and routes; do not remove the infrastructure
assertion guard to make a broad relevance score look better.

Next, map each relevant core profile group to an explicit sourced factor, activity
scope, route and eligible card role. Start with MU own manufacturing/product/customer
and sourced competitor context, then SNDK Consumer/Edge flash scope. Bound financing
by recipient/project and component availability by product market. Use this exposed
challenge and earlier regressions for development, then lock a new candidate on fresh
events. No title exceptions, reference rewriting or weight tuning is justified here.

Validation:47focused tests passed; CI46009475555 on codea914791 passed1317SQLite and
1317PostgreSQL tests, each with one existing Starlette warning, plus lint/type/JS,
migrations/seed/replay/downgrade, dependency audit and actual-model smoke. Candidate
remains NOT_PROMOTED; detailed data local, notifications disabled, services unchanged.
