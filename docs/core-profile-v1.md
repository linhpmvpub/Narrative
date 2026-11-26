# Core company profile v1

Decision frozen for the first implementation on 2026-11-25. Keep the database small and reusable; finish the database and algorithm before comprehensive performance evaluation. Separate LLM-prior usefulness/correctness evaluation is deferred by the user. Source checks, software tests and provenance remain required. No public rollout or live notifications.

## Seven core groups

| Group | Minimum useful content |
|---|---|
| Identity | Stable profile/company identity, ticker, legal name; historical profiles remain separate |
| Products | Products/segments and revenue model; scoped model or product family |
| Inputs | Named input/component/service, use scope, supplier where known; procurement/inventory/capacity as known modifiers |
| Output markets | Customer/end market, geography where relevant, demand/selling-price drivers |
| Counterparties | Named counterparties and competitors with documented relationship scope |
| Financial exposure | Sourced revenue/cost/debt context; numeric unit, denominator and period; labeled priors or UNKNOWN |
| Narratives | Watched products/factors, included/excluded developments and uncertainty |

`config/core-profile-v1.json` defines these groups and ten reusable relationship types: HAS_SEGMENT, SELLS, USES_INPUT, DEPENDS_ON, SUPPLIES, BUYS, SOLD_IN, COMPETES_WITH, HAS_METRIC, APPLIES_TO. Economic propagation stays in explicit mechanism rules; neither relationship presence nor a prior implies a measured profit effect. Existing richer relationship types and the42component catalog remain optional extensions, not requirements for every new company.

`engine.core_profile.project` produces a compact view referencing the existing atlas and input registry. It does not duplicate source facts or rewrite old profiles. Missing fields remain UNKNOWN. Input exposure IDs supplement the legacy component status; adding a product input does not falsely mark an entire broad component complete. Current projection has6profiles for5tickers, including a separate historical NVIDIA profile.

## Shared commodity/input/price registry

`engine.input_markets` stores CORE_INPUT_MARKETS_V1 in SQLite and JSON:

- Commodity: stable ID, explicit sourced aliases; no automatic parent/sibling inference.
- Exposure: company profile + existing product/segment/facility anchor + narrower product label/scope + USES_INPUT + quote. Product specifications establish supported input scope, not sales mix or a purchase contract.
- Price market: provider, instrument, SPOT/CONTRACT/RETAIL/INDEX, sourced unit/currency/geography or null. Definitions do not supply a price observation.
- Market link: same commodity ID and explicit BENCHMARK_PROXY_ONLY limitations. No equation of spot chip prices and server-module procurement cost.
- Source: HTTPS URL, immutable local capture/hash, retrieval time, optional publication time, CURRENT/WITHDRAWN/DISPUTED. Unknown publication date stays null.

The registry pins the atlas hash; changed atlas requires a new registry version. Evidence is checked against captured text, including table cells; interpretation of table columns and company/product scope is explicitly reviewer-declared. Review expiry is at most90days. Source withdrawal/dispute removes routing through dependent records. Current capture status does not establish perpetual publisher freshness.

Build a **new** directory for each version:

```powershell
python -m engine.input_markets --atlas <atlas-directory> --input <registry-input.json> --sources <capture-directory> --output <new-registry-directory>
```

Output: registry.db, registry.json, core-profiles.json, local source captures and a hash manifest. `read` validates integrity, exact quotes, identities and compatibility. Existing registry versions are not overwritten. To add another company: add its sourced atlas profile/product anchor, add scoped exposure records referencing existing commodities (or a genuinely new commodity), then rebuild. No company-specific matcher code is needed.

## First bounded population

| Company/product scope | Input | Primary evidence |
|---|---|---|
| Dell PowerEdge R760, R770 | DDR5 | [Dell memory architecture](https://www.dell.com/en-us/infohub/articles/ddr5-memory-bandwidth-in-dell-poweredge-servers-with-intel-xeon-6) |
| NVIDIA H100 SXM | HBM3 | [NVIDIA HGX specifications](https://docs.nvidia.com/enterprise-reference-architectures/hgx-ai-factory-h100-h200-b200/latest/components.html) |
| NVIDIA H200 SXM, B200 SXM | HBM3e | Same NVIDIA table, scoped columns |
| AMD Instinct MI300X | HBM3 | [AMD MI300X documentation](https://instinct.docs.amd.com/projects/system-acceptance/en/latest/gpus/mi300x.html) |
| Sandisk NAND storage business | Flash-based memory wafers | Existing locally captured [Sandisk filing](https://www.sec.gov/Archives/edgar/data/2023554/000162828026068601/sndk-20261002.htm) |

Totals:4commodities,7exposures across4companies,6source captures (5new public captures plus1existing filing),2market definitions and3proxy links. MU's generic materials record is retained; no guessed material recipe is added.

Market definitions: DRAMeXchange DDR5 16Gb (2Gx8) 4800/5600 spot quote and NAND Flash Wafer contract-price category. [Public price board](https://www.dramexchange.com/) and [provider methodology](https://www.dramexchange.com/Service/Faqs) ground their identity/basis. DDR5 chip spot is only a proxy for Dell's module inputs; NAND wafer contract category is not Sandisk's own contract. No HBM price benchmark is registered; that is an inventory gap, not a claim that none exists. No numeric price observations/time series imported in this task; unestablished currency/unit/geography stay null.

## News routing

```powershell
python -m engine.mechanism_playbook commodity --atlas <atlas> --input <observation.json> --selection <selection.json> --articles <article-root> --scope-store <source-ledger.sqlite> --input-market-registry <registry-directory> --output <local-cards.json>
```

`--input-market-registry` replaces legacy `--commodity-bindings`; they are mutually exclusive. Optional `--market-id` requires that exact instrument and market basis in the news, a compatible commodity link, and consistent known units/currency. Without it, registered markets are context only, not a claim that the news reports that benchmark. Source lifecycle, explicit period, >5% minimum and >=10% strong movement gates reuse the existing evaluator. Both directions are supported. Cards retain exact product scope/evidence, directly watched narratives and UNKNOWN financial magnitude/horizon. Multiple products of one company can yield distinct scoped cards; bundling belongs in the feed layer.

Current use is a local workbench. No active feed/map changes. One end-to-end demonstration uses a **synthetic12% HBM3 news event** with the real sourced registry and routes to NVDA H100 SXM and AMD MI300X only. This is a software integration check, not a real price move or independent benchmark.

## Next implementation, then evaluation

1. Use this fixed core in private feed/map and bundle same-event/product cards without losing scope/provenance.
2. Add bounded market observations/adapters with explicit series, unit, period and revisions; no broad commodity expansion until the current path works consistently.
3. Finish applicable source-lifecycle handling and end-to-end algorithm behavior, then run comprehensive evaluation and improvement loops. Do not launch a separate prior-evaluation workstream now.

## Local core workspace — 2026-11-26

`/core` is a separate authenticated-data workspace linked from `/news` and `/map`.
It shows the seven-group profile projection, sourced input → scoped product → company
paths and an event/company feed. The old canonical causal graph is not reclassified.
Profile component summaries retain the original status; registry input paths do not
silently mark all legacy components complete.

The API `/api/v0/news/core` is disabled unless `CORE_WORKSPACE_MANIFEST` points to a
local JSON manifest. Paths must resolve beneath its parent, including symlink targets.
Format: `atlas`, `registry`, `events` (at most100). Each event has a unique `id`,
`mode` (`RSS_CURRENT`, `MANUAL_RESEARCH`, `SYNTHETIC`), `observation`, `selection`,
`articles`, `store`, and optional `market_id`. Paths are relative to the manifest.
The manifest is operator-maintained, not accepted from API clients. Keep it under
ignored source-cache. Only the current event revision belongs in the manifest; event
IDs must remain stable on correction. Do not load cached result exports as live cards.

Every refresh validates atlas/registry and reruns commodity source/period/threshold
checks. RSS mode requires the current ingestion connection; manual research remains
explicitly labeled and is not a live-source freshness guarantee. Synthetic events are
excluded by default, including on logout. Same-event/company cards are combined only
when revision, measurement, commodity, selected market and all common decision fields
agree; each product scope/evidence/market limitation and narrative ID remains present.
This bundles product duplicates, not semantic duplicate articles from different sources.

The browser keeps the access token in memory, clears data on errors/logout, rejects
late responses after a new refresh/logout, and uses text nodes/HTTPS-only source links.
No auto-polling, notification delivery, cloud deployment or old-server restart occurs.
For local use configure the manifest in a separate process bound to127.0.0.1; do not
attach it to a tunneled service. Current local manifest is
`source-cache/core-workspace-2026-11-26.json`. Browser validation intercepts localhost
HTTP with the actual local projection; it is not a claim that a deployed server changed.

Current local result:6profiles,7sourced paths,0real price cards;2AMD/NVDA cards only when
synthetic mode is explicitly selected. There is still no normalized real price series,
company purchase price, exposure weight, financial magnitude or time-horizon estimate.
Next implement bounded sourced price observations with unit/instrument/period/revision
identity, then connect their reviewed observations to this manifest. Comprehensive
algorithm/database evaluation remains later; no separate LLM-prior evaluation now.

## Real RSS bridge and local runner (2026-11-26)

A core manifest can add `profiles`: a relative local directory containing current
company bundles. The RSS bridge uses only profiles whose model digest matches the
atlas. `CORE_WORKSPACE_DATABASE_URL` selects the news database independently of API
authentication. Defaults remain opt-in; no server is reconfigured automatically.

`engine.core_pipeline --manifest <local.json> --database sqlite:///<local.db> --output
<new-local-directory> --poll --price-board` polls configured RSS, projects current
source-backed matches, audits seven core groups and optionally captures a public DDR5
spot board. Set DEV_INFORMATIONAL_FEED=true only in that local process; keep delivery
flags false and LLM_MODE=none. Use the module with `python -m engine.core_pipeline`.

CORE_DECISION_V1 assigns conditional mechanism context from typed path relations,
not headline sentiment. Group by canonical article URL/profile; retain narratives and
source paths, stable ID and separate revision digest. No semantic cross-article dedup.
Raw capture required; source last success must be within1hour. Truncated paths and
paths beyond2hops are withheld. Feed scan capped500rows/100upstream cards and visibly
marked when truncated. Recency ranking is not economic materiality. No RSS topic card
becomes a price alert without the existing measured-change gates.

Price-board records retain exact chip instrument, SPOT basis, source timestamp,
session average, quote and capture hash. Same capture is idempotent; changed captures
at the same observation timestamp remain separate revisions. No automatic current-head
selection or inferred units, currency, comparison period or company purchase price.
Those missing fields block numerical alerts; the price series is not yet complete.

Current result is an end-to-end real RSS context flow, not completion of every item
in steps1–3. Financial exposure/counterparty gaps, normalized price series, calibrated
priority and measured matching quality remain open. Raw records and detailed audits
are ignored local artifacts; only aggregate progress is committed.

## Steps1–3 implementation contract (2026-11-26; supersedes earlier pending entries)

| Requested step | Implemented behavior | Intentional unknown / later acceptance |
|---|---|---|
| Core company database | Six pinned profiles/five issuers, seven groups,13existing financial sets,39scoped parameter facts,8entity references exposed with original source/period | Undisclosed hedge/contract/impact weights remain UNKNOWN; no mandatory42-component fill |
| Real ingestion→cards | Current captured RSS, dedup/revision/withdrawal, up to5000rows/1000candidate cards per bounded run, visible truncation, current price-series heads and1/7/30day windows | Actual free history currently2daily points; missing periods never synthesized |
| General decision algorithm | Same-window change/negation/forecast checks, entity/sector/background/sponsored tiers, explicit priority weights, source-duration bins, threshold price candidates through exact commodity registry | Editorial weights not empirical calibration; source duration not causal impact lag; financial magnitude unknown without applicable facts |

Core profile projection references authoritative atlas facts rather than silently replacing
legacy component status. Financial partitions are contextual data, not automatic exposure
weights. The current counterparties list includes only existing resolved references;
unnamed counterparties remain unknown. `financial_context`/`exposure_parameters` on cards
are scoped context, not newly verified causal coefficients.

Core manifest optional fields: `price_series` (local relative directory) and
`price_metadata` (local relative JSON). `engine.price_series.append` validates exact
instrument/date/column parsing and appends revisions, retaining immutable raw captures.
Identical observations are idempotent. `observations` verifies capture/record hashes;
`compare` uses the latest current observation and latest baseline at/before the requested
window, within3days of that target, exposing actual endpoints. A withdrawn point is not
silently replaced by an older active point. Latest price must be at most7days old.
Historical import is allowed but never makes a stale latest point current.

Metadata contains file/hash/exact quote, instrument,basis,currency,unit,known_at,review_until.
`basis_kind` is SOURCE_DECLARED or CROSS_SOURCE_INFERRED; inference additionally requires
inference_steps=1 and explanatory notes. Metadata and capture live in the same directory.
The user authorized cross-source inference on2026-11-26. Source-declared and inferred
units remain visibly separate; inferred units never become independently verified prices.
Metadata expiry invalidates use. Numeric primary prices are never overwritten or averaged
with secondary values. Registered market identity/basis and known units must agree.

If absolute change>5%, generate scoped conditional cost candidates; >=10% is a price-move
band, not company impact strength. Purchase price, financial magnitude and impact lag
remain unknown. At/below threshold creates no alert. Same-period correction replaces the
projection; source withdrawal suppresses it. No real delivery is enabled.

Run locally with a new output directory:
`python -m engine.core_pipeline --manifest source-cache/core-complete-workspace-2026-11-26.json --database sqlite:///source-cache/core-live-2026-11-26/news.sqlite --output <new-local-output> --poll --price-board`
Set DEV_INFORMATIONAL_FEED=true for that local process. The read-only API uses
CORE_WORKSPACE_MANIFEST and CORE_WORKSPACE_DATABASE_URL only when explicitly configured.
Never point an old tunneled service at local detailed data without authorization.

Implementation readiness is not v1 release acceptance. Next stages remain product
personalization, operational observation and comprehensive grouped evaluation/calibration.
