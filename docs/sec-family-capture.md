# SEC event attachments and amendment scope

Run `python -m engine.evaluation.sec_family_capture --audit <sealed-held-challenge> --root <workspace> --output <private-new-directory> --user-agent "Project contact@example.com"` to capture linked event attachments. The existing bounded SourceClient serializes requests at no more than two per second, applies response/retry limits and refuses redirects. No database, graph, feed or notification writes occur.

The plan verifies the sealed source-audit hash and original stored bytes before requests. Only literal HTTPS SEC HTML paths within the original issuer/accession directory are allowed. Traversal, encoded paths, alternate hosts, query strings, fragments and unsupported document types are rejected. Requests are capped at 100 per family and 200 per run. The command captures linked 8-K documents; annual-report amendment families remain primary-document reviews and do not trigger downloading the entire annual exhibit list.

Captured text is written once as UTF-8 bytes, with URL, content hash and actual retrieval time. SourceClient's default rights label is deliberately replaced with `pending_review`. A resumed run verifies its plan, file hashes and clocks, skips successful captures and retries missing sources. Missing attachments keep a family incomplete. An orphan file from interruption is not overwritten: preserve the directory for investigation and use a new run. Do not run concurrent writers against the same output directory.

Having every observed link downloaded does not prove exhibit inventory completeness, source truth or correct event grouping. `complete_exhibit_inventory_verified` stays false. Review primary Item 9.01, numbered exhibits, incorporated-by-reference material and any inaccessible/PDF attachments before allowing an evaluation packet. Source data and individual review notes stay local.

## Amendment review

Compare original and amendment issuer, reporting period, stated explanatory scope and exact source spans. Keep the original immutable and attach the correction to its family. An issuer's assertion that other disclosures are unchanged is not an automatic verification of every original claim. Numeric observations must use the corrected source and preserve the prior version; source-scope review alone must not promote numbers or canonical events.

The current local AMD pair was independently audited by two AI source reviewers. They agreed on the exact original and corrected quote offsets and the limited presentation-correction scope. This is operational source reconciliation, not new blind benchmark labels, human gold or a production approval. Both disclosures were already read for this reconciliation and must be marked exposed in future sampling.

## Current collection

The 2026-11-23 local run contains 21 primary documents: 19 event filings and two documents in one amendment family. It captured all 19 observed event attachment URLs with zero acquisition errors. Fourteen event filings have linked HTML attachments; five have none in the observed links. All remain review-required. Raw sources and provenance are under `source-cache/sec-family-attachments-2026-11-23`; only aggregate receipts are committed.

Next, review exhibit completeness and underlying event identity before freezing further predictions. Earnings 8-Ks, attached releases and later 10-Q/10-K documents can describe the same economic period even when their filing/report dates differ. Exclude or group those families across previous evaluation packets; accession-only grouping is insufficient to claim an unseen benchmark.

Two independent AI source auditors subsequently checked all 19 event families and 38 captured documents (76 raw/text hashes). Both found narrow text context sufficient for each family; the union of their limitations flags 11 families with external/prior/redacted context. This does not certify complete contracts or commercial effects. Four earnings families share an issuer/economic period with previously reviewed packets and require overlap handling before another benchmark freeze. The sidecar review consensus leaves every family in EVENT_GROUPING_REVIEW_REQUIRED; it does not mutate the capture manifest or production state.
