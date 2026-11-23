# Held SEC source challenge

`python -m engine.evaluation.held_role_corpus --index <held-index.json> --metadata <SEC-collection> --root <workspace> --output <new-private-directory> --exclude-packet <previous-packet.json>` validates captured sources without fetching, approving, ingesting or dispatching anything. Repeat `--exclude-packet` for every earlier labelled packet. Keep all artifacts under ignored local storage.

The metadata collection must contain hashed SEC company-ticker and issuer-submission snapshots. Each held filing must agree with the captured accession, issuer, form, filing date and URL. Acquisition/availability clocks and source hashes are checked. Legacy Windows CRLF storage conversion is accepted only when reversing CRLF to LF reproduces the recorded content hash; the physical file hash is separately sealed in the audit. No source files are rewritten.

The report period from submissions supplies the issuer-period grouping. Periodic documents with a known amendment are withheld as a family, including the original, until a source review determines the amendment's scope. All 8-K event documents are withheld pending event and exhibit review. Same-accession HTML links are inventoried as candidates, not assumed to be complete exhibits or fetched automatically. Missing periods, duplicates and previously reviewed documents cannot become negative examples.

Eligible periodic passages use fixed named-party/scope/control sampling independently of predictions. One passage per issuer-period, prior-packet near-duplicate exclusions and explicit underfill apply. The shared archive freezer seals current profile versions, reviewer input and separate predictions. No company matching rules or predictions enter the reviewer packet. This is current-profile text relevance, not a historical as-of backtest, ingestion evaluation or evidence of current commercial relationships.

Two separate-context AI reviewers receive only a copy of the packet, a rubric and hash receipt. Use `profile_relevance.consensus` against the ORIGINAL pre-review freeze. Use `held_role_corpus.evaluate(output, labels)` to additionally check the source audit hash. Disagreement stays unresolved. AI consensus is not human gold or independence from pretraining.

## Local run, 2026-11-23

26 held documents yielded 5 eligible periodic documents, 19 event/exhibit holds and 2 documents in the AMD amendment family. The audit inventoried 65 same-accession linked-document candidates. Ten earlier packets were excluded. Five issuer-period passages produced 25 narrative pairs, with 2 named-party, 2 identity-scope and 1 control samples. This is underfilled relative to the requested 24 clusters, and does not demonstrate balanced positive/negative coverage.

Both AI reviewers agreed on 25/25 pairs: 3 relevant and 22 not relevant. Frozen results: TP2, FP0, TN22, FN1, unresolved0. Only three positive examples exist; precision2/2 and recall2/3 do not establish population accuracy. The missed pair concerns the NVIDIA customer-buildout narrative. No routing/profile tuning followed these labels.

The original immutable freeze is `source-cache/profile-held-roles-2026-11-23`. Its exclusion-count telemetry mistakenly recorded zero although filtering ran. A separate v2 verification corrected this to 34 and asserted identical packet and prediction hashes; the original pre-review freeze remains the evaluation reference. Both directories must be excluded in future sample discovery. Only aggregate reports are published; original text, predictions and reviewer rationales stay local.

Next: capture and review the linked 8-K exhibits, reconcile the AMD 10-K/A scope, then create a separate held packet. Preserve accession family and issuer-period groups so exhibits and originals cannot leak across evaluation splits. Treat this round as exposed development evidence after review.
