# Financial evidence and mobile preview

Schema0008 stores immutable, time-versioned CompanyFacts snapshots. The existing canonical filing lifecycle remains authoritative. Acquisition does not generate canonical economic claims or notifications. Public sharing excludes development notices.

## Extraction and replay

Run migrations with DATABASE_URL pointing at rie-dev-feed.db, then set DEV_INFORMATIONAL_FEED=true, SEND_NOTIFICATIONS=false, ALLOW_SYNTHETIC_LIVE=false and LLM_MODE=none.

```powershell
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m engine.financials --user-agent 'Narrative Research linhpm.vpub@gmail.com'
```

The collector requires existing verified issuer/source cursors from incremental collection. Cache is ignored under source-cache/financial-facts. Source capture hash, accession, filing identity, same-concept USD operands and explicit dates accompany every comparison. Quarter, six-/nine-month YTD and annual periods are kept distinct. Multiple contradictory values, incomparable periods/units, nonfinite values and pre-spin SNDK periods are withheld. Percentage change requires a positive prior value. Consolidated entity metrics must not be presented as segment revenue or margin.

Snapshot availability is actual ingestion time, not historical filing time. Historical as-of cannot see later snapshots. Retries are idempotent; corrections create snapshot versions. Latest empty snapshot removes outdated comparisons, and withdrawn/missing/canonically changed filings invalidate them. Canonical filing history and financial snapshot history are separate.

Feed returns financial_assessments; map returns economic_observations and separate reported_metric nodes. Source links, JSON pointers, SHA256, filing and comparative periods are inspectable. Reported increase/decrease is descriptive: causal attribution is NOT_ESTABLISHED, stock-price impact/materiality UNKNOWN and narrative stance INSUFFICIENT_EVIDENCE. Source data does not establish causal graph verification.

## Remote phone access

The user approved Cloudflare for the prototype and confirmed remote phone access. The application stays at127.0.0.1:8888, with a read-only gateway at127.0.0.1:8890. Start gateway in the same development environment:

```powershell
.venv/Scripts/python -m uvicorn engine.mobile_gateway:app --host 127.0.0.1 --port 8890 --no-access-log
source-cache/bin/cloudflared.exe tunnel --no-autoupdate --url http://127.0.0.1:8890 --allowed-mail linhpm.vpub@gmail.com --protocol http2
```

Cloudflared2026.11.1 was downloaded from its official GitHub release and SHA256 verified:341deda3db5ec498a0482254d6c38c0b7cf01a30c37bb5dd95d2216d08955e35. Binary/logs remain ignored. Never drop allowed-mail: email OTP is the outer access restriction. The browser separately needs the existing member access token from ignored secrets/development-feed-access-token.txt to see private data. Do not include tokens in URLs, logs, commits or chat. The gateway forwards only explicit authorization/content-type headers to the fixed loopback backend; it never injects the member token. Admin, docs, sharing and editing routes are unavailable. UI hides write controls; scenario and idempotent owner refresh are allowed. Rate/body bounds and application authentication still apply.

Temporary URL is saved locally in ignored secrets/mobile-preview.json. Open its /map path after email OTP; root / is the feed. The PC and both local services plus tunnel must stay running. Restarting a quick tunnel changes its hostname; this is a temporary prototype, not permanent hosting. See official documentation: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/ .

## Validation and next work

Reports financial-mobile-state.json and financial-provenance-check.json record36 comparisons,72 raw operands checked and0 alerts. Full SQLite/PostgreSQL suites each passed265 tests; focused final suite passed13. Browser scripts use .audit-venv with installed Chrome and local preview credentials; they must run against a migrated development database, never a public unauthenticated server.

Next: independently evidenced causal relationships and segment drivers, cross-accession amendment linkage, and holdout evaluation with human labels. Current passing tests establish software behavior, not market prediction accuracy.
