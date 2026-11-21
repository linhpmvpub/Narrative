# Segment evidence and independent evaluation

## Implemented scope

Schema0009 adds immutable filing evidence snapshots keyed by ticker/accession/version. The collector imports the existing SEC collection receipt and verifies raw HTML SHA256, source URL, CIK, canonical identity, active source status and capture time. No network acquisition or new canonical event is required. Rights do not block this user-authorized private prototype. Real notifications remain disabled.

Inline XBRL extraction retains explicit StatementBusinessSegmentsAxis members, optionally accompanied by OperatingSegmentsMember. Product/geography/typed/multi-axis breakdowns are deliberately withheld. USD scale/sign and supported numeric transformations are explicit. It compares only the same concept, dimension tuple, unit, accession and comparable duration; current/prior context IDs and fact IDs survive into API/UI. Conflicting duplicate values, unsupported formats, nonfinite values and SNDK pre-spin comparisons are withheld. Fact labels use the issuer taxonomy member; no invented mapping to preexisting graph nodes. Operating income is not automatically relabeled operating margin. Quarter/YTD/annual figures remain separate. Same-member comparisons do not independently prove unchanged segment composition: reviewer must check recast disclosures.

CompanyFacts only covers standard concepts applying to the whole entity; dimensional evidence therefore comes from each Inline XBRL filing. References: [SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SEC context guidance](https://www.sec.gov/newsroom/whats-new/osd-announcement-contexts-september-7-2016).

## Causal verification boundary

Narrative paragraphs with explicit attribution language are captured with normalized paragraph index/hash and raw source hash. Their presence is verified against the captured source. ISSUER_ATTRIBUTION means issuer explanation, not independently established causality. Possible/negative/forward-looking language gets UNCERTAIN_OR_FORWARD_LOOKING. This is a deterministic screening heuristic; incomplete negation, multi-sentence scope and confounders require review.

Selected candidate graph relationships receive source_matches only when all configured lexical anchors occur in that paragraph. This is a retrieval aid, not verified support, sign determination or causal identification. The UI exposes full source text and status. No relationship status, strength, confidence, routing eligibility, stance or provider delivery changes. There are zero independently verified causal relationships from this pass. Do not promote issuer language automatically, infer margin from revenue, or equate change in segment income with stock-price effect.

Every read respects snapshot available_at and canonical identity/lifecycle. A withdrawn or changed source immediately hides its evidence; historical as-of still sees the earlier state. Empty replacement snapshots remove stale extraction. Canonical/source version history stays separate. Owner-scoped private feed/map only; public stories do not expose development notices.

## Commands

Use DATABASE_URL=sqlite:///rie-dev-feed.db, DEV_INFORMATIONAL_FEED=true, SEND_NOTIFICATIONS=false, ALLOW_SYNTHETIC_LIVE=false, LLM_MODE=none.

```powershell
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m engine.filing_evidence --collection source-cache/sec-review-2026-11-20/collection.json
.venv/Scripts/python -m engine.evaluation.filing_labels --output source-cache/evaluation-segments-v1
```

Use a fresh output directory on subsequent exports; do not overwrite labels. Captures, databases, tokens and full annotation packets stay ignored. A source hash mismatch aborts that filing; other files still receive explicit results. Existing preview8888 was restarted with0009; gateway8890/tunnel remain in place.

## Annotation protocol

The prepared local packet has204 cases:72 segment comparisons and132 financial narrative paragraphs. AMD/SNDK form a preliminary issuer-held-out partition; all versions of each issuer remain together. There are60 language cases in holdout. This small corpus is not representative market validation. Its sources were available during implementation; reserve genuinely unseen future filings before asserting generalization.

Give reviewers blind-cases.json and raw source captures/receipts only. Keep sealed-predictions.json out of their workspace. Predictions and labels must never feed production matching or change the graph. Two distinct human reviewers, independent of the extractor and of each other's initial labels, should annotate:

1. Language: ISSUER_ATTRIBUTION, UNCERTAIN_OR_FORWARD_LOOKING or NO_CAUSAL_CLAIM; preserve paragraph/source context, distinguish historical statements from risks/expectations, record counterevidence and reason. Each label includes case_id, reviewer, independent_of_extractor=true, reviewed_at (aware ISO time), source_sha256, label and reason. The declaration is auditable metadata, not proof of reviewer independence.
2. Numeric segments: independently transcribe concept, complete dimensions, current/prior values and start/end dates, USD scale/sign, period basis and whether the comparison is valid. Check segment recasts, definitions, overlap and reconciliations. Do not copy model outputs. Record ambiguous/invalid cases with reasons.
3. Causality: verify the proposed mechanism, direction, timing, conditions, alternative explanations and evidence from independent sources. A company repeating its own claim is not independent corroboration. Record supports/refutes/insufficient rather than forcing a positive edge.

The evaluate(pack, labels) Python function scores only holdout language classification with at least two agreeing independent reviewer declarations. Duplicate reviewers, unsupported cases, wrong source hashes, absent rationale and invalid review times fail closed. Disagreements remain pending adjudication. Report coverage and disagreements alongside accuracy on consensus; incomplete consensus is not final corpus accuracy. Numeric and true causal validation remain manual adjudication pending; market accuracy is always null in this evaluator. Current labels.json is empty: no human labels were fabricated.

Evidence reports: segment-collection.json, segment-retry.json, segments-provenance.json, segment-label-packet.json and segments-browser.json. The144 numeric operands were separately checked against source fact/context values and dates;275 attribution paragraphs have hashes/indices,28 candidate relation matches. None is a verified causal approval.

Next: obtain independent annotations and adjudicate disagreements; add external corroboration/contradictions and cross-accession amendment/recast linkage before promoting graph relationships. Expand product-level dimensions and margin derivation only with explicit semantic mappings and accounting basis.
