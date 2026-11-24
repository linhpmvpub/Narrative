# Personal company and narrative reading choices

In local `/news`, open **Theo dõi của tôi**, select companies and/or shared research
narratives, choose whether to show only followed items and include archive context,
then save. Choices survive reload/login and are owned by the authenticated account,
not shared with other accounts in its tenant. Nothing is selected automatically.
The existing temporary company/narrative filters still narrow the displayed result.

Preferences affect only eligible full-article research cards. Ordering is explicit:
followed narrative, followed company, discovery; within each group, fresh-window
items, company mentions and publication time, with a stable ID tie-break. These
are personal reading priorities, not financial importance, confidence or impact.
Source expiry, corrections, withdrawals and profile gates run before personalization.
Following an unavailable source cannot restore it.

## Storage and API

Migration `0017` adds `rie_article_preferences` to the **account database**. Run
`alembic upgrade head` there before restarting the API. The separate news inbox
does not store these preferences. Existing canonical subscriptions and private
user-authored narratives are not changed or automatically mapped to profile targets.

Authenticated GET/PUT `/api/v0/news/article-preferences` use the caller's principal;
there is no client-specified user/tenant. PUT requires `Idempotency-Key`, an
`expected_version`, bounded ticker/narrative arrays and strict boolean options.
The existing per-account transaction lock serializes writes. Retry returns the
same response; stale versions and key reuse with different content return 409.
Unknown targets are rejected. Previously saved but now unavailable targets may be
retained or removed, so a temporary catalog outage does not erase user intent.

GET `/api/v0/news/profile-articles` reads account preferences separately from its
configured source inbox and returns reason labels on ordered cards. Default empty
preferences preserve discovery and archive visibility. “Followed only” with no
choices intentionally returns no cards. The UI does not store tokens/preferences
in localStorage and clears private selections on logout/account connection.

The existing mobile gateway does not expose these new endpoints. Data remains
local; no push provider or cloud synchronization is enabled. This is persistent
selection of shared research narratives, not yet creation of personal theses or a
financial recommendation system.
