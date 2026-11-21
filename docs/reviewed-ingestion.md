# Reviewed SEC ingestion — schema 0006

The operator API can now turn an independently reviewed extraction into canonical event records. It runs entirely from stored captures, without fetching URLs, using an LLM, scoring, projecting a feed or sending notifications. All endpoints require a provisioned global operator and mutations require `Idempotency-Key`.

## Separate permissions from extraction review

An approved extraction receipt alone is insufficient. An operator must explicitly record source rights and issuer identity for the exact filing capture using:

`POST /api/v0/admin/sec/filings/{filing_id}/permissions`

Required fields: `expected_permission_version` (0 initially), `status` (`approved` or `revoked`), the exact ten-digit `cik`, an HTTPS SEC `evidence_url`, substantive `rights_note` and `identity_note`, `identity_confirmed`, and timezone-aware `valid_until`. Approval requires identity confirmation and a future expiry. There is no client-supplied effective/recorded time: permission starts when recorded, cannot be backdated, and is scoped to the capture hash. This is an explicit operator attestation; the application does not infer licensing from SEC availability or verify rights by downloading the evidence URL.

Subsequent permission changes append a version, requiring the previous permission version number. Revocation blocks further ingestion without deleting historical receipts/events. The existing source status is mirrored to `blocked` on revocation. Renewal is explicit, never automatic. `GET /filings/{filing_id}/permissions?as_of=...` returns recorded permission history visible at that cutoff. Global ticker aliases/graph permissions are not silently approved by a capture permission.

## Ingest a reviewed draft

`POST /api/v0/admin/sec/drafts/{draft_id}/ingest`

```json
{
  "expected_version": 1,
  "expected_permission_version": 1,
  "as_of": "<actual UTC cutoff, after source permission and extraction review>"
}
```

The example cutoff is a placeholder, not a valid timestamp to paste. Use the actual current UTC time; future cutoffs are rejected. Ingestion checks:

- Database is explicitly non-synthetic; settings still disable LLM and delivery.
- Expected draft remains the latest filing version, with independent approved review and complete proof.
- Published/captured/imported/drafted/reviewed clocks are consistent and visible at the cutoff; publication and capture are not interchangeable.
- Stored capture/text hashes, cited passage/offsets/URL, entity, metric issuer, units/period/basis and recomputed canonical identity still agree.
- Source permission exists and is active at both cutoff and processing time, with the expected current version; no missing, expired, revoked or mismatched permission is accepted.
- Any correction/reprint references an already-ingested earlier capture of the same canonical identity. The referenced extraction and permissions must still be valid. A correction changes facts and targets the latest canonical version. A reprint retains identical normalized facts and may attach to an older version without reverting the latest correction.

Canonical creation, document/evidence provenance and ingestion receipt commit atomically. Database-level writer serialization and uniqueness constraints prevent duplicate canonical events from concurrent operators. A conflicting existing canonical identity requires explicit duplicate/correction review; the service does not merge facts by guessing from headlines.

Successful responses include `event_id`, `event_version_id`, `draft_id`, status (`ingested`, `duplicate`, `versioned_correction`), real `recorded_at`, requested `as_of`, `feed_eligible=false`, and `delivery=disabled`. A receipt records input hash, permission/review IDs, operator and linked document/evidence IDs. Same-key retries acknowledge the original committed result; different-key retries recheck current gates and reuse the existing receipt without adding a version. A historical acknowledgement is not a statement that source permission remains active today.

## Time semantics and operator snapshots

The request cutoff is an **admission cutoff**, not the date at which the system pretends ingestion happened. Original document publication/capture timestamps are retained. Canonical event/version availability is recorded at ingestion processing time. Unknown exact occurrence time, evidence-quality score and materiality remain null/UNKNOWN rather than being invented.

`GET /api/v0/admin/sec/events?as_of=...` is an operator snapshot of these canonical versions, not a user feed. It shows only versions actually ingested by that cutoff and checks source permissions and extraction versions as they stood then. A subsequent revocation hides the event in the current snapshot while retaining earlier audit snapshots. If the latest canonical version is ineligible, the reader withholds it rather than silently reverting to an older version. It exposes the primary source only; later reprint evidence is not leaked into earlier snapshots.

## Local operation and limits

Run `alembic upgrade head` with the intended review DATABASE_URL to apply 0006. The local `rie-sec-review.db` was backed up into ignored `backups/` before migration. The operator preview/API remains on loopback port 8886; public nginx ingress continues to block `/api/v0/admin/`. UI extraction review remains available, while permission and ingestion operations in this milestone are API-only (see `docs/openapi.json`).

The 50 captured real filings remain unapproved: no real permission, draft or event was fabricated during development. Automated tests exercise the pathway using explicitly fabricated evidence in separate disposable stores. Correction/reprint links currently follow the review workspace's cross-capture policy; amendments to an extraction within the same capture need a separate future workflow.

Next step: gated private-feed projection from canonical records, including current rights/review validity, verified graph paths and calibrated materiality. This milestone does not enable notifications or bypass unresolved image-security/production-release gates.
