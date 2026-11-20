# Relationship & Impact Engine v0 — Codex implementation handoff

**Version:** 0.1.0 | **Prepared:** 2026-11-19 | **Language:** Vietnamese (product) / English (machine contracts)  
**Purpose:** A reproducible, explainable engine that tracks economic relationships and narrative hypotheses for 5 US equities, judges whether new evidence matters, and supplies Threadnote-compatible feeds and story timelines.

> This is a **build specification and seed/test package**, not a completed software implementation. All demo events are explicitly synthetic. All relationships are candidates until evidence has been checked. Never treat illustrative scores/weights as calibrated probabilities or investment advice.

## 0. Executive decisions (locked for v0)

| Area | Decision |
|---|---|
| Pilot companies | MU, NVDA, AMD, DELL, SNDK |
| Pilot narratives | Exactly 10, 2 per stock; see `config/narratives.json` |
| Coverage | Economic links in AI infrastructure / compute / memory / storage; maximum 2 hops |
| Runtime | Python 3.12, FastAPI + Pydantic v2, PostgreSQL 16, SQLAlchemy 2 + Alembic, pytest, Docker Compose; optional local OpenAI-compatible LLM adapter |
| UI | No frontend rewrite; JSON endpoints consumable by existing Threadnote UI |
| Database | PostgreSQL adjacency edges, no Neo4j; event sourcing and versioning for audit |
| Data sources | SEC EDGAR and approved company IR as primary sources; licensed news and market prices optional adapters |
| Ranking | Transparent rule-based scoring + hard gates, no numerical event-outcome probability |
| Updates | push/digest/story-only/suppress; in v0 dry-run by default; no real phone pushes without explicit switch |
| Narrative states | SUPPORTS, CHALLENGES, MIXED, NO_CHANGE, INSUFFICIENT_EVIDENCE |
| Historical test | point-in-time only, evidence available at replay timestamp; no future-looking source |
| Production safeguard | user auth, tenant separation, idempotent writes, secrets via environment, source provenance, no raw copyrighted article republishing |

### Why these stocks?
These five generate useful intersections in the AI compute—servers—HBM/DRAM—NAND/SSD supply chain. **SNDK is independent from WDC from February 2025**: do not merge WDC historical HDD activities, financials, or identifiers into Sandisk. User's earlier IONQ/JPM/WMT pilot can be added after this concentrated graph-engine experiment; it is intentionally out of scope for v0.

### Success is not "a clever summary"
A credible v0 must (a) surface an important *indirect* event with a source-backed causal path, (b) suppress noise, stale and duplicate coverage, (c) explain uncertainty, (d) produce a reproducible per-narrative timeline, and (e) improve through auditable feedback without blindly rewarding attention.

## 1. Scope / non-goals

### In scope
1. A typed set of entities and economic relationships with provenance, direction, effect modifier, state and validity dates.
2. 5 verified ticker identities and 10 narrative seeds with indicators, supporting/challenging conditions and monitoring boundaries.
3. Evidence ingestion via SEC/IR adapters, with a deterministic fixture mode (fixtures **must work offline**).
4. Event normalization, event clustering/deduplication and graph matching up to 2 hops.
5. Gate-based evidence quality, materiality/relevance/novelty scoring, stance determination and dispatch decision.
6. User/thread subscriptions, structured feedback, decision logs, review queue, storybook timeline and read-only integration endpoints.
7. Backtest replay with strict `as_of` cutoff, golden test suite, baseline comparison and quality reports.

### Excluded
- Price targets, buy/sell recommendations, portfolio execution, personalized advisory signals, pseudo-probabilities of doubling.
- Broad internet crawling, scraping paywalled/copyrighted transcripts, unauthorized distribution of news text.
- 3+ hop causal chains; market-wide instant coverage; production web/mobile push integration; a complex ML training pipeline.
- Automated learning that promotes unverified edges or modifies live thresholds without review.
- A claim that all 10 narratives are currently true; they are hypotheses.

## 2. Product contracts and onboarding

A **stock thread** watches a ticker and relevant material changes. A **narrative thread** watches a user-approved hypothesis. Reuse the same source event and graph, but render two distinct explanatory contexts. Do not duplicate a notification to a user when one event matches both; allow a single notification with `also_relevant_to` and multiple thread IDs.

Free-tier entitlement is a separate application-level rule: **3 stocks and 1 narrative**. V0 stores entitlements but does not implement billing. The 10 pilot narrative seeds are selectable templates; they do not imply 10 free user subscriptions. Users may create custom narratives only if the editor constrains them to a subject, horizon, <=3 high-priority drivers, >=1 disconfirmation condition, and <=2 graph hops; otherwise prompt to narrow.

**Narrative workflow:** user writes one sentence -> optional LLM proposes structured narrative -> user reviews -> compiler resolves drivers to known entity IDs -> checks monitoring scope -> activates. Do not treat arbitrary narrative text as a trusted graph query.

## 3. Data methodology: relation graph, not a pile of keywords

### 3.1 Entity classes
- `company` (MU, NVDA, AMD, DELL, SNDK), ticker as separate time-bound alias (not canonical ID).
- `product_market` (HBM, DRAM, NAND, enterprise SSD, AI accelerators, servers).
- `driver` (AI_CAPEX, HBM_DEMAND, NAND_ASP, etc.).
- `financial_metric` (MU_GROSS_MARGIN, DELL_ISG_MARGIN, etc.).
- `policy_or_constraint` (EXPORT_CONTROLS, ADVANCED_PACKAGING_CAPACITY).

### 3.2 Exactly six relation families
`CUSTOMER_DEMAND`, `SUPPLIER_COST`, `COMPETITOR_SUPPLY`, `PRODUCT_MARKET`, `MACRO_POLICY`, `FINANCIAL_TRANSMISSION`.

Each directed edge must have: stable ID; from/to; family; `mechanism`; `sign` (`positive|negative|conditional|unknown`); `lag` (`immediate|short|long|variable`); `strength` in 0..1 only as an initial *routing heuristic*; `confidence` in 0..1 as separate *evidence confidence*; status (`candidate|verified|rejected|stale`); evidence IDs; valid/recorded dates; review owner/decision. No verified promotion with empty evidence. A verified relationship is not a guarantee that an event's economic impact materialized.

**Candidate seeds:** `config/relationships.json` uses `candidate` by default, `strength=null` in live data and a separately labeled synthetic `demo_strength`: they provide graph structure for Codex and synthetic tests, **not verified real-world company-specific exposures**. Code must not push through candidate edges. Seed a separate opt-in `demo_mode` in which approved synthetic verification is simulated, with obvious demo flag and no real-world notifications.

### 3.3 Verifying edges
For each candidate edge: search company 10-K/10-Q, earnings release, slide deck or an approved licensed source; record citation URL, document date, extracted passage offsets, `observed_at`, and coverage dates; label sign and confidence. If disclosed, set `exposure` (such as relevant share of revenue, volumes or operating costs) with a numerical denominator and fiscal period, and `sensitivity` (effect per measurable change), keeping both independently sourced. If exposure/sensitivity are unavailable, `strength` stays null until a reviewer chooses and documents a **qualitative routing band** (`low|medium|high`) with uncertainty. Never pretend that the strength heuristic is a calibrated elasticity or probability. If exposure numbers are not disclosed, store `null` and cap impact assertions. Record conflicting disclosures with review status instead of selecting the desired interpretation.

**No fabricated bilateral claim**: e.g., 'NVDA buys a material percentage of MU HBM' is not acceptable unless explicitly evidenced. Use sector-level `accelerator demand -> HBM demand`, and demonstrate relationships through observable mechanisms rather than silently asserting specific customer contracts.

### 3.4 Two-hop routing
Consider only `event_entity -> A -> narrative driver` with up to 2 verified edges. Different paths may be correlated; use **best path**, not a sum of path scores. Example strength heuristic: path relevance = `product(edge.strength)` × `0.85^(hops-1)`; confidence is separately `min(edge.confidence, source_confidence)`; a condition-dependent/unsigned edge cannot establish a definitive directional conclusion. Direct issuer disclosure matching the ticker or a driver may be routed as hop 0, while materiality is still independently checked.

Never infer stock-price direction from an economic relation graph. Economic impact and expected market response are distinct.

## 4. Ten pilot hypotheses

Detailed machine-readable contracts: `config/narratives.json`. Each narrative contains:
- `narrative_id`, `ticker`, `title`, `thesis`, `horizon_months`
- `driver_ids` (max 4 seeded, max 3 priority drivers for custom free tier)
- `supporting_evidence` and `challenging_evidence` (observable signs, not assertive facts)
- `metrics`, `watch_entities`, `disconfirmation`, `known_confounds`, `update_cadence`
- `version`, `created_at`, `status`, `is_template`.

| ID | Stock | Title | Primary disconfirmation |
|---|---|---|---|
| N01 | MU | HBM demand and premium mix drive profitability | HBM demand increases but MU mix/margin fails to improve |
| N02 | MU | Memory supply cycle threatens pricing power | DRAM capacity rises yet DRAM ASP/margin remains resilient |
| N03 | NVDA | AI capex sustains accelerator demand | AI spending increases but NVIDIA orders/revenue do not follow |
| N04 | NVDA | Supply/export constraints limit growth | Constraints ease or demand reallocation offsets restrictions |
| N05 | AMD | Instinct adoption expands AI accelerator revenue | Adoption fails to convert into repeat shipments/revenue |
| N06 | AMD | EPYC share gains improve data center business | Reported server CPU progress fails to help segment economics |
| N07 | DELL | AI server orders convert into profitable revenue | Backlog fails to convert or segment margin dilutes |
| N08 | DELL | Component inflation compresses infrastructure margin | Pricing/pass-through offsets cost inflation |
| N09 | SNDK | NAND price recovery supports earnings | NAND ASP recovers without sustained margin or cash improvement |
| N10 | SNDK | Enterprise SSD demand expands higher-value mix | SSD demand rises but Sandisk economics/mix do not improve |

**Stance semantics:** Each narrative includes `hypothesis_polarity_for_company` (favorable/adverse). A new event SUPPORTS/CHALLENGES a *claim's conditions*, not necessarily the stock. In particular, SUPPORTS an adverse-risk thesis (N02, N04, N08) is potentially **negative for the company**, not bullish. This is separate from any stock-price prediction. Both directions in one event => `MIXED`; if directional mechanism is unverified => `INSUFFICIENT_EVIDENCE` or `NO_CHANGE`. No cumulative "probability narrative is true" in v0.

## 5. Event model and ingestion

### 5.1 Data sources & scope
- SEC EDGAR `data.sec.gov/submissions/CIK##########.json`, XBRL CompanyFacts when concept mapping is known, filing excerpts (10-K/10-Q/8-K). Discover ticker/CIK mapping from current SEC company ticker feed and persist snapshots; never use ticker as immutable legal identity.
- Company IR press releases and investor presentations, via explicit allowlist with source URL + license review.
- Prices: optional licensed adjusted OHLCV adapter, default `UNAVAILABLE` rather than mocked market prices in live UI.
- News: optional compliant licensed provider; store article metadata, URL, short factual claims, not copied full text.
- No earnings transcript full-text ingestion unless rights are confirmed.

Use a descriptive `User-Agent` and throttle EDGAR requests below SEC's published maximum of 10 req/sec; suggested **2 req/sec** with exponential backoff and caching. SEC APIs do not require authentication. Sources: https://www.sec.gov/search-filings/edgar-application-programming-interfaces and https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data .

### 5.2 Event schema
Required: `event_id`, `canonical_event_key`, `source_document_id`, `primary_entity_id`, `event_type`, `occurred_at` (nullable), `published_at`, `first_seen_at`, `available_at`, `headline_factual`, `claim`, `metric`, `old_value`, `new_value`, `unit`, `period`, `comparison_basis`, `source_span`, `evidence_ids`, `extraction_model_version`, `is_synthetic`. All values use decimal-safe types where practicable; source/filing values retain declared units and fiscal calendars. Distinguish three clocks: event occurrence, publication, and information availability.

Deduplication: normalize by issuer + event kind + metric + reporting period + occurrence/window; exact URL/content hash handles same document; cross-publication event cluster handles multiple headlines about the same economic fact. Later **material corrections** create a new *version* of the canonical event, not a duplicated original alert. An explicit correction notification may be sent once for the newly corrected version (with a correction badge and link to prior alert); ordinary reprints cannot create new event versions.

### 5.3 Extraction rules
- No numeric comparison without same concept/units/calendar basis or an explicitly documented conversion.
- Do not conflate GAAP and non-GAAP, backlog and bookings, guidance and actuals, price and fundamental metric, quarterly and annual reporting periods.
- Source span/source document citation mandatory for any quantitative or directional statement.
- Preserve contradictory evidence; flag for review; do not manufacture a confident stance.
- Do not directly publish LLM-generated freeform text; require validated `EventExtraction` Pydantic JSON and deterministic consistency checks.

## 6. Decision engine: deterministic first

### 6.1 Hard gates (all before scoring)
1. `source_rights=approved` and retrievable provenance; `is_synthetic=false` for live channel.
2. Valid data identity; no future-dated evidence in replay; known publication/availability times.
3. Event is not an already-delivered canonical event version for that user.
4. Relevant path of length 0–2; for indirect path every relation must be `verified` and valid as of decision time.
5. No unresolved contradictory core numbers, unit/period mismatch or unverified material financial claim.
6. `evidence_quality >= 0.70` to enter digest scoring; push additionally requires `>= 0.80`.
7. Materiality cannot be `UNKNOWN` for live push; unresolved materiality can enter review/digest with transparent language.

### 6.2 Initial v0 scoring (heuristic, must be calibrated later)
`score = 100*(0.25*R + 0.20*M + 0.20*N + 0.15*Q + 0.10*T + 0.10*U)` where R relevance, M materiality, N novelty, Q evidence quality, T timeliness, U user fit in [0,1]. Store all components, extraction/policy versions, selected path and gate decisions in an immutable `decision_trace`.

Rubrics:
- `R`: direct issuer exact driver match ~1; verified one-hop via primary driver ~0.7–0.9; verified two-hop ~0.4–0.7, constrained by edge strength; candidate edge 0 and no push.
- `M`: quantitative impact estimated by *specific metric* materiality rubric and historical percentiles/baseline, otherwise `UNKNOWN`; no universal “+10% is material” across all indicators. Use expert-review event-class fallback only in review mode. Store scale and horizon.
- `N`: unseen new disclosed fact 1; revision of prior fact 0.6–0.9 if materially different; previously announced information repeated 0–0.2.
- `Q`: SEC/official primary extract with auditable passage may score 0.9–1; approved secondary provider with corroboration 0.7–0.9; uncited assertion 0.0. Quality is evidence for factual claim, not certainty about future effects.
- `T`: age since `available_at` with event-type-specific half-life, filing events longer than trading-related short-lived updates; no universal 24h cutoff.
- `U`: narrative driver/filters match, user feedback preference, suppress known/irrelevant categories; do not permit U to override safety gates.

Thresholds: `score >=80` => push candidate (if all push gates pass); `60..79` => digest candidate; `<60` => story-only/archive. Push requires a narrative stance (`SUPPORTS|CHALLENGES|MIXED`), not just a rising score. Multiple articles on same event must not inflate score. Store suppressed candidates too, for recall evaluation.

### 6.3 Effect reasoning
Separate `relevance` from `direction` from `realized_outcome`. If an edge is `conditional` or event doesn't meet trigger, stance `INSUFFICIENT_EVIDENCE`. Conflicting material evidence => `MIXED`. Emit structured explanation:
1. factual delta vs comparison baseline;
2. path showing `event -> driver -> company metric`;
3. support/challenge/unclear and why;
4. counter-explanation or missing data;
5. next falsifiable check;
6. exact evidence URLs and publication timestamps.

No `probability`, price target, expected return, assertive cause of share-price movement in v0.

### 6.4 Dispatch
Single event across multiple subscribed threads for one user should be bundled into one delivery with `also_relevant_to`, sorted by highest score. `candidate` is not `sent`: v0 dry-run default, `sent_at` remains null until provider confirms. Store `push`, `digest`, `storybook`, `suppressed`, `review_required` categories independently from delivery statuses. Offer per-user quiet hours in local time, daily notification cap, batching, and admin kill switch. Newsworthy issuer filings should never bypass evidence gates just because they're recent.

## 7. Feedback and continuous improvement

UI labels: `USEFUL`, `ALREADY_KNEW`, `NOT_RELEVANT`, `UNCLEAR`, `WRONG` (WRONG should create high-priority verification ticket). Store `user_id`, `notification_id`, `label`, optional `reason_code`, `free_text`, `created_at`, `model_version`; allow updates/corrections while retaining audit history.

Two independent models:
- **Global quality:** factual errors, missing evidence, duplicate class, source confidence, relation-path correctness, missed material events (expert or verified labels); do **not** adjust truth/confidence from likes.
- **Personal relevance:** explicit user feedback, alert opened/dismissed, selected narrative drivers, preferences; limited to ranking/filtering user-specific items. Don't equate clicks with truth.

Never auto-promote an edge or retrain production scoring from a few feedback samples. Aggregate issues weekly, produce change proposal with offline replay on frozen gold dataset; require review before release. Record previous and next values, reason and evaluator dataset version. Sample suppressed events for human review to measure false negatives (selection bias mitigation).

## 8. Storybook as an audit product

Each story entry is derived from a verified event+decision; immutable factual snapshot tied to sources, narrative version at time of publication, and a `state_delta` (`supports|challenges|mixed|no_change`). Entries sorted by `available_at` not invented event chronology. Revised source facts append corrections and reference original entry; do not silently overwrite. Plot:
- Optional licensed adjusted price series with precise timestamps, corporate-action adjustment info.
- SEC quarter/year financial series only as discrete observations with `period_end` and `first_available_at` (no daily interpolation of revenue/profit).
- Narrative milestones, driver values, open questions, and corrections.
- Shareable story export **off by default/private**; public publication requires explicit opt-in and removal of user-private notes.

## 9. API contract (v0 JSON)

All user endpoints require authenticated user context and tenant checks. Admin routes additionally require admin role. Make OpenAPI docs available. Errors structured `{code, message, request_id}`. Cursor-based pagination for feeds. No silent fallback to demo data.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/v0/stocks` | list 5 pilot stocks / metadata |
| GET | `/api/v0/narratives/templates` | list 10 narrative templates |
| POST | `/api/v0/narratives` | create custom narrative, schema validation, set `draft` until reviewed |
| POST | `/api/v0/subscriptions` | attach a user to a stock/narrative respecting entitlement |
| DELETE | `/api/v0/subscriptions/{id}` | unsubscribe, preserve history |
| GET | `/api/v0/threads/{id}/feed` | decision cards, provenance, event state |
| GET | `/api/v0/threads/{id}/story` | timeline and date-scoped metrics |
| POST | `/api/v0/alerts/{id}/feedback` | upsert current feedback, append audit event |
| POST | `/api/v0/admin/fixtures/replay` | admin dry-run fixture replay, idempotent |
| POST | `/api/v0/admin/relations/{id}/review` | approve/reject relation after evidence review |
| GET | `/api/v0/admin/review-queue` | events/edges requiring review |
| GET | `/api/v0/admin/eval-report` | baseline quality and release comparisons |
| GET | `/healthz` and `/readyz` | process and dependencies |

Example narrative feedback response: `{ "id":"...", "status":"recorded", "used_for":"personal_relevance_review", "global_truth_modified":false }`.

## 10. Tech architecture / Windows installation

```
SEC/approved IR + offline fixtures
      |
[Source adapters] -> [Documents & provenance] -> [Structured extraction]
      |                                      |
      +----------------------------------[Event normalization + dedup]
                                              |
[Relationship graph] + [Narrative compiler] -> [1-2 hop matcher]
                                              |
                                    [Evidence + score + gates]
                                              |
                   +-------------[Decision trace/review queue]----------+
                   |                                                    |
               [Feed API]                                         [Gold evaluator]
                   |                                                    |
             [Feedback API]                                      [Change proposals]
                   |
           [Storybook builder]
```

Use FastAPI/Pydantic, PostgreSQL + SQLAlchemy/Alembic. For v0 scheduled processing, database-backed job table + small Python worker or OS cron/container scheduler; prefer **no Redis, Kafka, graph DB, vector DB or agent swarm initially**. Optional LLM adapter must be pluggable (`none`, local OpenAI-compatible/Qwen, remote) and constrained to JSON with validation; all fixture tests run with no model and no internet.

Windows dev: Windows 11 + WSL2/Docker Desktop recommended. `docker compose up -d db`, Python venv, `alembic upgrade head`, `python -m engine.seed --config config`, `pytest -q`, `uvicorn engine.api:app --reload`, `python -m engine.replay --fixture fixtures/events.jsonl --as-of 2026-11-01T00:00:00Z --dry-run`. Codex must implement these CLI commands or document precise working equivalents. Configuration through `.env.example` (never commit secrets).

**Integration policy:** inspect existing Threadnote repository before changing anything. Add engine as isolated module/service. Preserve existing UI routes and user data; require migration and compatibility tests. If no existing repo available, create standalone service with mock client requests and a minimal read-only Swagger interface.

## 11. Model prompts and quality rules

Define 3 separate LLM roles with explicit JSON schema and deterministic validators; never allow the same generated free-text reasoning to validate itself:
1. `EVENT_EXTRACTOR`: turn allowed source text into facts with offsets, timestamps, units, metric, comparison period and source IDs. `unknown` instead of inventing.
2. `RELATION_PROPOSER`: suggest typed relation candidate, signed/conditional mechanism and a source requirement. ALWAYS status=`candidate` until evidence review.
3. `EXPLANATION_WRITER`: receive *validated* event, verified path, structured stance, scoring trace and approved evidence; write <=3–4 short sections (what changed, why connected, impact, what next), no new facts.

A fourth independent `EVALUATOR` may flag errors or unsourced claims but cannot approve sources without deterministic provenance check. All externally sourced strings are untrusted data: prevent prompt injection, strip markup/script instructions, reject requests inside source documents that attempt to change system policy. Limit sizes/timeouts and store model/provider/version/prompt hash for reproducibility.

## 12. Replay evaluation and target criteria

### 12.1 Datasets
- `fixtures/events.jsonl`: synthetic and explicit, for acceptance/regression only. Never shown as live news.
- Human-curated historical **50–100 real events** across 5 tickers; include 30% negatives/irrelevant/reprints, and at least 20 indirect-edge cases. Collect genuine publication timestamps and archive identifiers.
- Split historical by time: initial development (earlier period), calibration (later), holdout (latest). No event/doc from after cutoff may influence a replayed decision. Freeze holdout before tuning.

### 12.2 Gold labels and baselines
Labels: `is_new`, `is_relevant`, `is_material`, `valid_path`, `stance`, `should_push`, `should_digest`, `reason`, `evidence`. A human reviewer should be able to inspect and correct every label. Compare three variants on the **same as-of corpus**:
- B0 keyword match + recency.
- B1 direct ticker + LLM summary (no graph).
- V0 graph + hard gates + scoring.

Metrics: push precision, material-event recall, false pushes per stock/week, recall of indirect relevant events, duplicate alert rate, citation traceability, factual-error rate, useful feedback among respondents (reported separately with response rate), cost per processed event, p95 latency, evaluator agreement and review time. Avoid claiming learned performance improvement without holdout evidence.

### 12.3 Acceptance targets (hypotheses, not industry benchmarks)
- 100% of alerts have source citations and reproducible reason/path; 0 synthetic alerts sent to real user.
- >= 90% push precision and >= 80% recall on *labelled material events* on holdout; report confidence intervals and counts, do not exaggerate small samples.
- No critical invented numeric or company-customer assertions; no SEC/IR timestamp leakage into historical replay.
- Duplicate same-canonical-event deliveries to same user = 0; user isolation tests pass.
- Corrections logged with linked prior versions; rejected/candidate edges never produce an indirect live push.
- New feedback NEVER changes global factual truth automatically; replay tests on both accepted and suppressed events.
- Offline fixture tests 100% pass; CI lint/type/SQL migrations pass.

If performance thresholds are not met, return evidence-based diagnosis and do not declare product-ready.

## 13. Risks and mitigation

| Risk | Mitigation |
|---|---|
| False causal links | Typed relations + verified evidence + max 2 hops + conditional semantics |
| Event flood | Canonical event dedup + per-user bundling + notification cap + quiet hours |
| Data license/IP | Source rights metadata + metadata/citation-only output + approved provider adapters |
| Historical look-ahead | `available_at` point-in-time snapshots for documents, edges, metrics and narrative versions |
| SNDK vs WDC identity confusion | Independent entity IDs, 2025 effective dates, no inherited pre-spin financial attribution |
| Local LLM Qwen inaccuracies | JSON schema, unknown allowed, numerical deterministic checks, strict hard gates |
| Feedback poisoning | Separate user relevance from global truth, rate-limit, aggregate + audit |
| Subscription abuse / expensive custom narratives | Scope quotas for driver count, compute caps, scheduled digest, shared event computation |
| Personalized advice | Informational thesis-monitoring only; counsel review before financial-product launch |

## 14. Implementation phases / Codex deliverables

### P0 — Repo audit and architecture lock (0.5–1 day)
- Detect current Threadnote stack, reuse auth/database patterns and naming.
- Produce `docs/architecture_decisions.md`, `.env.example`, `docker-compose.yml`, runnable skeleton, CI template.
- No unrelated refactors; verify no existing user data migration changes.

### P1 — Database, seed identities and contracts (2–3 days)
- Migrations for entities, aliases, source docs, evidence, relations, narratives, drivers, events, decisions, subscription, feedback, story entry, evaluation and audit tables.
- Load 5 stocks + 10 narratives + candidate graph from JSON. Validate IDs, duplicates, referential integrity and temporal fields.
- Tests for SNDK/WDC separation and correct stock/narrative cardinality.

### P2 — Ingestion & canonical event pipeline (3–4 days)
- Offline fixture loader first; SEC submissions/CompanyFacts adapter second; company IR adapter with allowlist third.
- Store hashes, provenance, publication & first available timestamps; idempotent retries; event dedup, source span quality checks.
- Tests for reprints, corrections, stale event, mismatched quarterly/annual values, SEC rate-limit/backoff.

### P3 — Graph matching, ranking, stance (3–4 days)
- Verified-only max-2-hop query; path/exposure trace, conditional propagation, evidence gates, six scoring features, push/digest/archive/review.
- Replay timestamps; compare B0, B1 and V0 on frozen fixtures; record every suppressed decision.
- Tests for candidate-only edge, missing data, uncertain sign, contradictory evidence, multiple correlated paths.

### P4 — Feed, feedback, storybook, Threadnote API (2–3 days)
- Authentication, subscriptions, feed/read API, feedback store, story timeline API; client-friendly responses.
- User dedup across threads; dry-run notification job; private timeline by default.
- Tests for cross-user isolation, duplicate deliveries, corrections, story-as-of consistency.

### P5 — Gold evaluation & release candidate (4–6 days)
- Curate 50–100 real historical events with reviewer labels and source URLs; ensure they are genuinely available at replay timestamps.
- Benchmark keyword, ticker-only LLM and graph v0; confusion matrix per stock/narrative, review errors.
- Generate `reports/eval-v0.md`, `reports/cost-v0.md`, operational runbook, known limitations, go/no-go decision.

**Total indicative effort:** roughly 15–21 focused engineering days, not a delivery promise. Prioritize P0–P3 before a polished UI. Codex must stop and document blockers rather than substituting fictitious sources or silently relaxing thresholds.

## 15. Definition of Done

- [ ] 5 company records uniquely identified and separated from aliases; SNDK/WDC tests pass.
- [ ] Exactly 10 template narratives validated with support/challenge drivers and disconfirmation rules.
- [ ] Relationships are all traceable, versioned and not silently treated as verified.
- [ ] Valid source document -> normalized event -> approved path -> decision trace -> feed card -> story entry works end-to-end in fixture mode.
- [ ] `as_of` replay can reproduce a past answer with the evidence/graph state available then.
- [ ] 10+ acceptance edge cases pass, including duplicate, correction, stale, indirect and conditional.
- [ ] Feedback is recorded and used only by the correct learning path; no auto-change of truth.
- [ ] Live pushes disabled by default; user/admin auth and audit trail implemented.
- [ ] Evaluation report names failures and compares to baselines; no unsupported performance claim.
- [ ] One-command local setup and full test run documented for Windows/WSL2.

## 16. Source reference registry

Useful grounded starting points, not substitutes for citations attached to every derived assertion:
- SEC EDGAR API docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC fair access: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- Sandisk independent company (2026 filing): https://www.sec.gov/Archives/edgar/data/2023554/000162828026068601/sndk-20261002.htm
- Western Digital HDD/flash separation: https://www.sec.gov/Archives/edgar/data/106040/000010604025000038/wdc-20250627.htm
- Dell ISG products disclosure: https://www.sec.gov/Archives/edgar/data/1571996/000157199626000046/dell-20260731.htm
- Micron annual report: https://www.sec.gov/Archives/edgar/data/723125/000072312526000023/mu-20260903.htm

For company-specific claims about NVIDIA, AMD and actual bilateral exposure, retrieve and cite *currently available* issuer documents during implementation. The seed does **not** assume unverified customer contracts, market share values or actual 2026 earnings outcomes.

## 17. Package index

- `CODEX_START_HERE.md`: paste-ready Codex instruction, order of operations, stopping rules.
- `config/stocks.json`: stable company identities and product buckets.
- `config/entities.json`: complete typed node registry for all relationship and narrative IDs.
- `config/narratives.json`: ten machine-readable narrative hypotheses.
- `config/relationships.json`: candidate edges with *explicit verification needed*.
- `schemas/schema.sql`: reference logical PostgreSQL schema for Codex migrations.
- `schemas/json_contracts.json`: structured extraction, narrative, decision and explanation DTO contracts.
- `fixtures/events.jsonl`: synthetic fixture events including negative, duplicate and ambiguous cases.
- `fixtures/demo_verified_relationships.json`: isolated synthetic evidence/approval snapshot for offline graph tests; **never** import to live verified graph.
- `tests/golden_cases.json`: expected behavior cases for policy and graph tests.
- `codex/TASKS.md`: granular implementation checklist and acceptance criteria.

**Important:** Any new LLM integration, paid news feed, or real user notification requires an explicit environmental and rights review. No automatic production push from the initial package.
