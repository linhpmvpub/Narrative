# Event-scoped accounting impact cases

This path presents a real historical worked case from source acquisition through
exact financial normalization, declared AI review, arithmetic, private feed and
map. It does not approve a reusable causal edge, ingest a new canonical event,
predict prices or represent a prospective evaluation. First supported issuer is
NVDA/CIK1045810; extending issuer/concepts requires explicit implementation/tests.

`engine/accounting_evidence.py` reads bounded Inline XBRL without DTD/entities,
rejects duplicate IDs, matches issuer/USD/exact duration/exact dimensions, preserves
fact IDs/scale/precision, rejects conflicting repeated facts. Consolidated operands
are crosschecked with SEC companyfacts for the identical accession/period/value.
Prior-year comparisons enforce dates and comparable duration; week differences
remain explicit. This corroborates a filing representation, not an independent
causal source. Data Center is a reported product revenue category, not a verified
business-segment mapping or the affected fraction of company revenue.

`engine/impact_cases.py` computes the accounting identity revenue-cost=gross profit,
bounds the recognized charge by cost of revenue, and reports charge/revenue as a
conditional gross-margin magnitude holding all other terms fixed. This is neither
the full observed margin change, a non-GAAP reconciliation, lost sales, cash impact,
tax-adjusted earnings nor a stock-price forecast. The source mechanism remains
ISSUER_REPORTED, with limitations and per-gate decision trace. No arbitrary strength,
confidence, materiality threshold or global graph approval is manufactured.

Private artifacts live under `source-cache/impact-cases/<case>/`, configurable by
IMPACT_CASE_ROOT. Each case has case.json, exact UTF-8 source bytes, three declared
AI review artifacts and receipt.json sealing hashes plus actual availability time.
File hashes are checked on each read; revisions require new inputs/reviews rather
than replacing sealed evidence. Withdraw by status=withdrawn in the current local
receipt; current revocation hides the case even for a past cutoff. This is a
conservative current-valid reader, not immutable historical review replay. Hash
receipts are local integrity evidence, not external timestamps/signatures. Local
operator-controlled files remain trusted configuration; no remote write route.

The member endpoint GET /api/v0/news/impact-cases and live map expose only computed
allowlisted case data; no review notes/actor identity/filesystem paths. Read-only
gateway permits the case GET only. Refresh/hide/logout clear old case displays;
unavailable/tampered sources or review files withhold the case. Backend/schema0016,
canonical counts and40 candidate graph edges remain unchanged. Private source data,
review files and case records are never included in GitHub or Pages artifacts.

Three user-authorized AI personas independently checked the first case: retail and
fund received sources/spec, no computed output or each other's vote; expert checked
both votes and source, no computed output. All accepted REPORTED_ACCOUNTING_CASE
only. A Windows newline packaging issue was caught by review; exact bytes were
restored from original SourceClient JSON captures and all raw hashes rechecked.
No source content or review target hash was altered to fit a result.

Prospective evaluation remains separate. The frozen protocol requires filings dated
on/after2026-11-23 UTC. Its preflight currently returns WAITING, with0 new predictions
and0 labels. Do not include this2025 case in that holdout or alter the locked protocol.
After eligible documents arrive, collect, prepare, publish the hash anchor BEFORE
blind labels, adjudicate and evaluate per docs/prospective-pipeline.md. All agreement
with AI references must remain distinct from human/causal accuracy.
