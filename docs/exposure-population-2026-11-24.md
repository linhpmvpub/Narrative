# Sourced company exposure population — 2026-11-24

This iteration expands the local research database before grouped news evaluation. It does not retune individual articles, identify undisclosed customers, calibrate impact strength, or change active feed profiles. Archived SEC evidence was manually reviewed by the implementing AI operator; this is not independent labeling or a fresh publisher verification.

| Company | Current profile | Sourced components before → after (of 42) | Exposure facts | Added context |
|---|---|---|---|---|
| AMD | v8 | 4 → 11 | 7 | Limited inputs, substitution, supplier prepayments; customer capital/power/water constraints |
| DELL | v6 | 7 → 14 | 6 | Contract manufacturing, recourse guarantees, procurement and rebates, FX and geographic revenue |
| MU | v3 | 5 → 15 | 8 | Manufacturing and utilities, qualification, supplier commitments, take-or-pay and pricing bands |
| NVDA | v12 | 11 → 17 | 4 | Direct customer concentration, headquarters geography, scoped H200 tariff pass-through |
| SNDK | v3 | 8 → 15 | 6 | Customer concentration, purchase orders, NBM contracts, Flash Ventures financing |

Historical NVIDIA remains separate and unchanged (6 sourced components). Across six profiles: 78/252 slots have some sourced evidence, up from41; current five profiles72/210. These counts do not measure completeness. Graph63nodes/69relations, versus49/55;31exposure facts versus3. All14added relations are structural context, not independently established causal effects. Seven shared mechanisms remain uncalibrated.

## Reported quantities and scope

- AMD: all CPU/GPU wafers at7nm or smaller sourced from TSMC (fraction1); not all company products or revenue.
- DELL: approximately40% net revenue from customers outside US in FY2027Q2 and first six months, each period; not end-user geography.
- MU: top10customers approximatelyhalf annual revenue in each FY2024/2025/2026; not one customer or three-year aggregate.
- NVDA: one unnamed direct customer16% of Q2FY2027 revenue; do not mix with first-half concentration or infer identity.
- NVDA:38% Q2FY2027 revenue from customers headquartered outside US; not delivery or end-use geography.
- NVDA: no H200 import tariff passed to customers in the cited disclosure, normalized0; not a general pricing elasticity or all-product margin assumption.
- SNDK: two unnamed customers each12% of revenue in three months ended2026-10-02; not12% combined.

Numeric input requires reporting period, measurement denominator/basis and exact-versus-approximate reported precision. Exact means normalization of the reported number, not infinite measurement precision. Period end cannot follow knowledge time. Legacy numeric fact inputs require these fields before rebuilding; old snapshots remain unchanged.

## Sources retained locally

- [AMD, period ended2026-09-26](https://www.sec.gov/Archives/edgar/data/2488/000000248826000191/amd-20260926.htm): supply and customer deployment paragraphs.
- [DELL, period ended2026-07-31](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000046/dell-20260731.htm): procurement, contract manufacturing, guarantees, geography and financing.
- [Micron, fiscal year ended2026-09-03](https://www.sec.gov/Archives/edgar/data/723125/000072312526000023/mu-20260903.htm): operating model, customer contracts and utilities.
- [NVIDIA, quarter ended2026-07-26](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/nvda-20260726.htm): quarter concentration/geography and H200 disclosure context.
- [Sandisk, quarter ended2026-10-02](https://www.sec.gov/Archives/edgar/data/2023554/000162828026068601/sndk-20261002.htm): customer concentration, NBM, procurement and venture financing.

Exact quotes, capture hashes, profile versions, reviewer and timestamps reside in ignored local artifacts. Public source URLs and aggregate inventory counts may be committed; raw filings, database, detailed profiles, labels and screenshots must not be uploaded.

## Local access and verification

Open `source-cache/exposure-expansion-2026-11-24/atlas-v4/index.html` locally. Choose a profile and inspect the sourced exposure cards for period, basis, scope and source quotes. SQLite, JSON and integrity manifest sit alongside HTML. No HTTP requests are needed; this is not the live news app or a remotely hosted map.

Focused regression suite:53passed. Edge smoke exercised five tickers, six profiles, all31fact cards, source evidence, narrative paths, filters,42component slots, seven mechanisms and390px mobile layout with no HTTP requests. Full CI45375976574 succeeded on codebb01fc0:896SQLite tests149.78s and896PostgreSQL tests267.28s; dependency audits, lint/type/JS and migration/seed/replay/downgrade passed. Final atlas-v4 integrity checks passed; three preexisting facts advanced toversion2 for added period metadata, with previous snapshots retained.

## Remaining work

1. Fill per-product/segment denominators, inventory and replacement lead times, contractual pass-through and effective dates where disclosed; preserve UNKNOWN otherwise.
2. Resolve shared supplier/customer/facility identities only from explicit evidence; unnamed counterparties remain unnamed.
3. Freeze a database version and build disjoint grouped event cohorts to test scope, relevance, causal channels, strength and horizon separately.
4. Calibrate relationship weights on independent labels, with sufficient positive cases across allfive companies. AI labels must remain distinguished from human gold.
5. Integrate reviewed candidate paths into product cards only after those gates. Real notifications and cloud data publication remain disabled.
