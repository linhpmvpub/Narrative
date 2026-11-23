# Reviewed SEC source roles in the private feed

`GET /api/v0/news/reviewed-roles` is an authenticated, read-only projection in the news page. It uses the same role/profile routing as the archive evaluator, with trusted issuer context coming from reviewed SEC ingestion rather than an RSS ticker.

Every read validates the latest canonical version, the current filing draft and independent review, current source permission and identity, ingestion receipt hash, exact extraction/fact content, document capture/text hashes and linked citation offsets. A newer canonical version, an unreviewed replacement, withdrawal/missing-source lifecycle, revoked permission or corrupted evidence hides the card. There is no rollback to an older valid-looking record. Profile source, narrative scope, expiry and path checks are also current.

Cards display buyer, purchased product, supplier wording, source quote/URL, original document offsets, profile path and decision trace. They do not expose private review notes or actor IDs. Role wording does not merge identities, approve a graph edge or establish current contracts, quantities, financial impact or causality. The UI clears cards when refresh fails, on logout and when the page loses visibility.

SEC drafts/reviews now declare AI/HUMAN/UNSPECIFIED provenance. Old records default to unspecified; they are not retrospectively called human-reviewed. New ingestion uses the neutral extraction-model name `independently-reviewed-sec-v1`. The browser explicitly labels independent AI review when declared.

The local worked pilot is a previously exposed historical NVIDIA FY2025 filing excerpt about purchasing memory from named suppliers. Two separate-context AI source audits independently checked raw and transformed hashes, issuer identity in the document, exact offsets and role direction. It was imported and independently reviewed under distinct temporary local operator accounts, then ingested without enabling delivery. Temporary tokens were revoked afterward. A pre-ingestion SQLite backup is retained locally. The resulting card concerns the Micron memory narrative and clearly retains the historical source date; it is not a new independent benchmark or a verified current customer relationship.

The source permission is scoped to the user-authorized local private prototype; commercial rights were not assessed. The original source acquisition time is preserved. Filing-date precision is not an SEC acceptance timestamp, and no strict historical replay eligibility is claimed.

New SEC candidates are staged separately and not automatically reviewed or ingested. Known URLs/hashes from indexed collections and profiles are excluded when building the next corpus. This is not proof against every possible prior exposure or model pretraining. Raw documents, audit files, credentials and detailed packets remain ignored/local; only code, synthetic tests and aggregate reports are pushed to GitHub.

Run the focused synthetic tests in `tests/test_reviewed_role_feed.py`. With the real local pilot present, `tests/browser_reviewed_roles.py` checks mobile/desktop display, AI disclosure, sources, failure/recovery and logout. Live notifications remain disabled. Next: build and lock a new role-balanced evaluation packet from the held source corpus before fresh independent labeling.
