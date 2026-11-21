# Private development feed

Updated continuation: see [incremental collection and impact map](incremental-impact-map.md).
Schema head is now0007; the limits/next-work section below records the original feed milestone.

This mode implements the user's 2026-11-21 instruction to temporarily bypass source-rights,
verified-graph and materiality gates for private development. It does not grant source rights,
approve evidence, score impact or send notifications. The reviewed ingestion path remains strict.

## Scope and provenance

The free [SEC submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
requires no API key. We use its filing metadata for MU, NVDA, AMD, DELL and SNDK, cross-checking
the SEC ticker index and submissions issuer. Network requests identify the contact, run at no
more than two per second, cap decoded responses at 5 MB and never follow redirects. No article
body or filing content is copied into this feed. A notice means a filing exists, not that a
particular economic fact was extracted or independently verified.

`DEV_INFORMATIONAL_FEED=false` is the default. Opt-in ingestion and projection require `true`.
`SEND_NOTIFICATIONS=false`, `ALLOW_SYNTHETIC_LIVE=false`, and `LLM_MODE=none` remain mandatory.
Use a separate non-synthetic database, currently `rie-dev-feed.db`; production database mode
means non-synthetic data, not release approval. No migration is needed beyond schema 0006.
The SEC review store and synthetic demo are unchanged.

Canonical keys have a `development_sec_notice:` namespace and issuer/accession identity.
Unchanged metadata is a duplicate; changed metadata for the same accession creates an immutable
version and correction link. Older cached captures cannot revert newer versions. Amendments
with a different accession remain separate notices; no unsupported economic-event deduplication.
The source remains `pending`, evidence quality is unset, no reviewed evidence or metric
observations are generated. Raw capture hashes and URLs are retained in document metadata. The document content hash
identifies the normalized notice plus capture receipt (including retrieval time), so a later
capture restoring earlier metadata remains a distinct immutable receipt.
Filing publication has date precision only. Actual capture, ingestion and projection times
control availability; an older filing never appears in a historical feed before processing.
Timeline ordering is knowledge time with a deterministic tie-break, not inferred publication time.

Projection matches only the issuer of an active stock/narrative subscription. It does not imply
that the notice supports or challenges that narrative. Cards explicitly carry `UNKNOWN`
materiality, `INSUFFICIENT_EVIDENCE` stance, no score/path, bypassed-gate traces and private labels.
No dispatcher or delivery provider is called. Existing owner/RBAC, temporal pagination, feedback
and correction history apply. Public stories exclude this event type **before pagination**, even
for previously enabled share links. Disabling the flag also hides development cards in private
feeds, while preserving their audit history. Feedback never grants approval.

## Run locally (PowerShell, project root)

```powershell
$env:DATABASE_URL='sqlite:///rie-dev-feed.db'
$env:DEV_INFORMATIONAL_FEED='true'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m engine.development_feed --user-agent 'Narrative Research linhpm.vpub@gmail.com'
.venv/Scripts/python -m uvicorn engine.api:app --host 127.0.0.1 --port 8888 --no-access-log
```

The initialized preview has DELL, NVDA, MU and N08 subscriptions. The ignored
`secrets/development-feed-access-token.txt` contains the provisioned 30-day token; paste it into
the login form, never a URL. Database initialization uses existing `seed` and
`initialize_review_store`; provisioning uses the existing account tooling. Do not reinitialize
or convert a synthetic database. Raw API cache is ignored under `source-cache/development-feed/`.

The CLI collects at most 20 notices per company (10 by default), reports partial company failures
and returns nonzero on any such failure. A five-minute source cache avoids immediate refetches.
Run the command again to collect new metadata. The UI refresh invokes authenticated
`POST /api/v0/development-feed/refresh`, an owner-scoped idempotent local projection; it makes no
internet requests. Newly subscribed threads receive existing notices only from that projection
onward. There is no automatic polling schedule. Sharing never includes these cards.

## Limitations / next work

This is an informational SEC filing feed, not full-text news extraction or verified impact
analysis. No withdrawal detection or cross-accession amendment grouping yet. The current small
pilot projects stored versions in memory; larger corpora need incremental bounded projection.
Next: add source filters and incremental collection/withdrawal handling, then extend to official
issuer releases with the same explicit provenance. The separately reviewed canonical impact-feed
path, independent benchmark labels and production release gates remain pending.
