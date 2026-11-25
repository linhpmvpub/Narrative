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
