# Local product-v1 collection and acceptance

This worker is an unverified discovery/review pipeline. It extends the existing reviewed canonical-event and profile-routing engines; it cannot approve relationships, derive impact, activate a dossier or dispatch notifications. The expanded catalog has 23 enabled endpoints: 18 RSS/Atom endpoints (including bounded older pages from the same publishers) and five SEC submissions endpoints. Endpoint count is not independent publisher coverage. Four X entries and the retired AMD URL stay disabled. No X API key is needed.

## Run in an isolated local database

From the repository root in PowerShell:

```powershell
$env:PYTHONUTF8='1'
$env:DATABASE_URL='sqlite:///source-cache/product-v1-pipeline/inbox.db'
$env:DEV_INFORMATIONAL_FEED='true'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
New-Item -ItemType Directory -Force source-cache/product-v1-pipeline | Out-Null
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m engine.market_pipeline --user-agent 'Narrative research linhpm.vpub@gmail.com' --cycles 1440 --interval 60 --capture-budget 8
```

1440 cycles run for approximately one day plus collection time, then exit. Ctrl+C stops foreground execution. The OS releases worker.lock on process exit/crash. Re-running resumes source cursors, revisions and article capture state. The local observation period is not seven days until receipts prove it. The server's existing private feed database/profile activation is unchanged.

## Pipeline

1. Poll due endpoints, at most four host groups concurrently and sequential requests within each host, at least0.5seconds apart. Reuse conditional ETag/Last-Modified; durable DB leases prevent duplicate polling. Failures retain old cursors and back off. Changed source URLs/issuer identity require new source IDs; retired AMD source remains disabled for audit.
2. Archive original feed bytes by SHA256 before database writes. RSS uses bounded XML parsing including declared Latin-1 and UTF16 BOM; DTD/entities remain forbidden. SEC verifies returned CIK/ticker and collects bounded recent10-K/10-Q/8-K metadata and amendments, not filing assertions. This does not yet collect Form4 insider filings. Empty results are valid, not fabricated coverage.
3. Deduplicate canonical URLs for discovery while preserving per-source items and correction revisions. Company names, active reviewed profile references and broader factor terms create discovery candidates. Public names and profile-topic matches are separate coverage metrics. Broad power/weather/materials themes are retained without inventing company exposure. Ten event families are unverified text signals; conditional/negative/quoted context stays flagged.
4. Diversify a bounded50-item extraction queue across company/theme buckets. Pin revision, version, payload/capture hashes. Capture up to8 allowlisted article pages per cycle. Reject stale/superseded queue entries; verify existing packets before resume; preserve corruption as failure; retry transient failures after cooldown. Captures are visible HTML text, not guaranteed article-only text or verified facts. Redirects are not followed automatically.
5. Store private snapshots, coverage, source health and receipts under source-cache/product-v1-pipeline. Source counts do not establish relevance recall. Broad thematic matching has no graph or notification eligibility. Current inbox scanning is bounded to10000 recently received rows; truncation is disclosed. The legacy freeze refuses inboxes above500 rather than silently testing partial routing; a larger paginated freeze is a remaining scaling task.

Outputs: latest.json, runs/, profile-plan.json, current-queue.json, queue/, queue-state/, feed-captures/, articles/. All remain ignored by Git. Background invocation may additionally write worker-process.json and worker stdout/stderr logs here; verify the PID/command belongs to this worker before stopping it.

## Profile evidence workbooks

```powershell
.venv/Scripts/python -m engine.profile_research --manifest source-cache/role-source-corpus-expanded-2026-11-23/collection.json --output source-cache/product-v1-profile-research
```

This validates local filing hashes, trusted SEC issuer URL scope, retrieval/date boundaries, and SNDK post-spin dates. The legacy SEC manifest hashes decoded UTF8 text with normalized newlines; a separate local-file byte hash is retained, not mislabeled original network bytes. Each of ten component areas contains bounded exact source-context candidates with text hashes/offsets, or explicit UNKNOWN. Keyword contexts require attribution, period and relation review. No candidate automatically becomes SOURCED or an active profile. Existing AMD/NVIDIA/Micron profiles and all prior frozen predictions remain unchanged.

## Frozen evaluation and gates

Set NEWS_CAPTURE_DIR to this worker's feed-captures before using engine.evaluation.profile_relevance. Freeze predictions before assigning two independent review contexts. Exclude all prior packets and near-duplicate article text; preserve the scope and hashes. Public launch cannot be inferred from AI agreement.

```powershell
.venv/Scripts/python -m engine.product_readiness --directory source-cache/product-v1-blind-2026-11-24 --review source-cache/product-v1-review-a-2026-11-24.json --review source-cache/product-v1-review-b-2026-11-24.json
```

Readiness recomputes consensus from original independent reviews and validates prediction/packet hashes. It reports unresolved cases separately, minimum positive/negative counts, relevant clusters by issuer, strata, precision/recall and descriptive Wilson lower bound. URL clusters still need independent economic-event grouping review, so that gate is explicitly pending. Operations require seven days of receipts without observation gaps over15minutes, adequate successful polls and fresh sources. This is local diagnostics, not externally attested uptime. No readiness output enables cloud deployment or delivery.

Current limitations: DELL/SNDK lack active reviewed narrative profiles; all five profiles have completeness gaps under the new standard. Supplier/customer attribution and numerical/period claims still require reviewed ingestion. RSS excerpts can omit necessary context. Source excerpts and all independent labels stay local; only code/docs/aggregate diagnostics may be pushed. No historical point-in-time accuracy or stock-price prediction is claimed.
