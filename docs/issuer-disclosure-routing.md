# Issuer relationship disclosures

An issuer can describe its supply network without reporting a price, capacity or financial change. `ISSUER_RELATIONSHIP_DISCLOSURE` bindings handle that informational context separately from the existing `ECONOMIC_CHANGE` rules.

Disclosure bindings retain reviewed evidence, product/topic and context terms, expiration and graph path checks. They require explicit first-person phrases and an approved list of narrative IDs. They cannot contain economic change terms or alias the first-person phrases. A supported route alone is insufficient to spread a supplier description into a customer-demand narrative.

The matcher requires a positive numeric issuer CIK supplied separately by a trusted source caller, equal to the profile CIK. It never reads issuer identity from a news payload. Only the bounded source paragraph is searched; quoted speech, competitor language and explicit negation conservatively withhold this mode. This is literal, reviewed contextual routing, not general language understanding or proof of a named supplier contract.

Currently the offline archive evaluator supplies the issuer from the integrity-checked SEC collection metadata. RSS has no such trusted issuer provenance and therefore cannot activate disclosure bindings. A future reviewed-ingestion integration must verify issuer identity before passing this context; do not copy an RSS ticker into that parameter. No production age, source, graph or delivery gates are relaxed.

Local NVDA profiles add memory, wafer and packaging disclosures restricted to supply-resilience. AMD disclosures retain the existing sourced TSMC/GF identity and product scope, restricted to foundry-resilience. These are current profile assumptions applied to archived text, not statements that today's relationship graph existed historically.

Development comparison uses the previously exposed 24-document challenge. An initial unrestricted version recovered the known supplier-network miss but also linked it incorrectly to customer buildout. Explicit narrative scope addresses that failure. Intermediate profile versions and the preliminary unreviewed freeze remain local and immutable; only the subsequent scoped freeze is sent to independent reviewers.

For follow-up, `archived_profile_relevance --exclude-packet <previous/packet.json>` verifies the earlier packet hash and excludes every source document in it, plus near-duplicate text. Both reviewers see only the final packet/rubric/hash receipt. These are different documents from the previous challenge, but they came from the historical archive previously used by the project, so this remains retrospective AI diagnostic evidence, not human gold or a pristine historical holdout.

No new relationships, orders, numerical impact or notification eligibility are created. Source language ambiguity, unmodeled issuer phrasing and limited positive examples remain limitations. Evaluate further changes on other documents instead of rewriting frozen predictions after seeing labels.
