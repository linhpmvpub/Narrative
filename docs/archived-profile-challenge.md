# Archived text, current-profile relevance challenge

This offline evaluation reuses captured SEC filings to test whether text can be connected to a current company narrative. It accelerates discovery of missed relationships without waiting for tomorrow's RSS. It does not estimate historical trading performance, point-in-time recall, event novelty or production push accuracy.

Run `python -m engine.evaluation.archived_profile_relevance --archive <local-archive> --output <new-local-directory> --count 24` with the local profile feature enabled. The archive must contain the original collection, blind-input packet, freeze receipt and captured documents from the historical replay workflow. Collection/packet/document hashes and actual acquisition times are checked; source paths cannot escape the archive.

Sampling uses fixed named-party, identity-scope and control vocabulary, independently of engine predictions. One passage per issuer/report period is selected round-robin, excluding previous labelled passages and word-trigram near duplicates. Strata are sampling categories, never relevance labels. Original excerpts and source issuer/period are retained; documents were previously exposed and are explicitly marked as such. Cross-period issuer observations remain correlated.

Predictions use the same literal term, entity-context and temporal path primitives with current reviewed profiles. This is a text-stage benchmark: old articles are not inserted into the news database and production age/ingestion gates are not disabled. Current knowledge must never be presented as available when the historical filing was published.

The immutable packet omits matching rules and predictions; those live in a separate hashed file. Two fresh-context AI reviewers receive only its copy, rubric and hash receipt. First-person wording belongs to the filing issuer. A named competitor does not imply a supplier or customer. A source-scoped conditional exposure can be relevant without a realized financial event. Disagreement remains unresolved, not adjudicated by the implementation agent.

Use the existing `profile_relevance consensus` command for two declared independent review files, then pass `--labels <consensus-file>` to this module. The archive-specific evaluator preserves the correct track and limitations. Save only aggregate receipts to Git; captures, full packets, predictions and individual rationales remain local. No feed/graph/notification writes occur.

This challenge is diagnostic development evidence. Once reviewed it is exposed; do not tune on it and call its results a holdout. Next validation needs different source documents or an explicitly separated held-out archive with source-time profiles if claiming point-in-time performance.
