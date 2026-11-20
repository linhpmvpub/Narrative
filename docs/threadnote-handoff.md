# Threadnote integration handoff

The actual Threadnote repository has not been supplied. The standalone OpenAPI contract is exported to `docs/openapi.json`; endpoint behavior, ownership, idempotency and narrative versions are documented in `docs/integration_api.md`. No unrelated local project or frontend was modified.

Integration needs a reviewed server-side mapping from the host's authenticated user/tenant to provisioned engine identities. Do not trust a browser-supplied user/tenant header, expose global operator tokens to clients, or use the legacy catalog token for private API calls. Test cross-user and same-tenant isolation against the actual host identity provider before release.

Frontend work: subscription quotas/confirmation, draft scope review and immutable approval versions, source-linked cards with conditional versus actual stance, source-time timelines, linked corrections, private feedback, and explicit public-sharing consent/revocation. Render external text as text, not executable HTML. Preserve synthetic labels and disabled-delivery status in every demo view.

Suggested first integrated pilot: one private account subscribes to DELL and N08; a trusted operator runs isolated synthetic replay; both threads show one shared canonical F021 card with R026→R027, insufficient evidence, conditional cost impact and no delivery. Verify correction/feedback/ownership/sharing workflows with a second account. This is a private fixture pilot, not historical performance validation.

Commit/publishing handoff requires the user's Git author name/email and remote URL. Local Git has been initialized, with secrets/cache/virtual environments excluded, but no identity or remote is fabricated and no push is claimed.
