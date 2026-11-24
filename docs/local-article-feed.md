# Reviewed full-article research feed

The authenticated `/api/v0/news/profile-articles` endpoint projects reviewed source
bodies into the `/news` reading interface. It remains research relevance, not
accepted impact, confirmed company exposure, or push eligibility. The existing
active company registry and other feed sections are unchanged.

The section supports company and shared-narrative filtering, source excerpts,
profile evidence and uncertainty. It clears cards at refresh, failed reads, logout
and page visibility changes. Temporary filters are session-local; account-owned company/shared-narrative choices
are described in `personal-reading.md`. The mobile gateway intentionally does not allow
the new endpoint; access is localhost only until remote data access is authorized.

## Operator setup

Set `DEV_INFORMATIONAL_FEED=true`, `SEND_NOTIFICATIONS=false`,
`ALLOW_SYNTHETIC_LIVE=false`, `LLM_MODE=none`. Set `DATABASE_URL` for the collector
command to the local news inbox. For the API, keep its account database unchanged
and set `ARTICLE_FEED_DATABASE_URL` to that same inbox. `ARTICLE_FEED_ROOT` defaults
to `source-cache/article-feed`. It contains private manifests and immutable state
history, never committed to Git. Profile and article roots are explicit per build;
the API never changes global environment variables during a request.

Install an explicitly reviewed selection set (1–100 articles) into a new root:

```powershell
python -m engine.article_feed install --selections LOCAL_SELECTIONS --profiles LOCAL_PROFILES --articles LOCAL_ARTICLES
python -m engine.article_feed refresh
```

For a bounded worker, `refresh --cycles 96 --interval 900` checks every 15 minutes
for approximately 24 hours. This is a local process, not a durable Windows service.
Restarting the machine ends it. A source check expires after one hour; cards then
disappear until a successful recheck. No external network requests run in feed GETs.

## Corrections and withdrawals

Install starts `AWAITING_RECHECK`. A refresh first marks entries `CHECKING` and then
captures each allowlisted HTTPS URL without redirect/access bypass. Equal normalized
visible text becomes `ACTIVE`; changed text becomes `REVIEW_REQUIRED`; an explicit
publisher withdrawal becomes `WITHDRAWN`; inaccessible sources become `UNAVAILABLE`.
404/403/network errors are not evidence of a publisher retraction. Whole-page text
comparison can conservatively hold unchanged stories when navigation changes.

Every GET rechecks source hashes, capture/time proof, one-hour TTL, current profile
evidence and inbox anchors (item identity/version/hash/source enabled state). Inbox
corrections, new conflicting copies, deletion or withdrawal hide the old projection
immediately on the next GET. A manifest change during projection also fails closed.
Detection is bounded by collector/refresh cadence; it is not instant publisher truth.

Changed/withdrawn entries never recover automatically, even if the publisher reverts
to old bytes. Capture the replacement and review its complete body boundaries anew,
then supply exactly one selection in a local JSON array:

```powershell
python -m engine.article_feed approve-replacement --selections NEW_REVIEWED_SELECTION
python -m engine.article_feed refresh
```

Replacement requires a different capture and a review later than the previous review
and source check. It returns to `AWAITING_RECHECK`, never directly to active. Existing
RSS withdrawal must also be resolved before replacement. Old states and captures
remain. CLI approval is a local operator declaration, not independent financial or
causal verification. No remote mutation route was added.

An exclusive writer lock serializes changes, and immutable `state-vN.json` snapshots
precede atomic pointer replacement. If interrupted with an orphan snapshot or lock,
hold the feed and reconcile the last complete snapshot locally before restarting;
do not delete history or silently overwrite it. The expiry gate remains in force.

For a pinned queue, escaped source diff and conflict-checked review packet, use
`python -m engine.article_review queue`; see `local-article-review.md`.
