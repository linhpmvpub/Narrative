# Incremental private feed and relationship/impact map

The user's development instruction defers source-rights review. No copyright approval is
required to collect or display this private development feed. Source identity, provenance,
time, correction history and uncertainty still matter for algorithm quality. Live notifications
remain disabled. This milestone does not claim calibrated stock-price predictions.

## Collection and lifecycle

Migration **0007** adds per-company collection checkpoints and immutable run receipts.
Each company reconciles atomically under the existing shared ingestion lock; failures roll back
both events and checkpoint. Captures older than the committed primary snapshot are rejected.
An exact replay returns its receipt without new versions. The first batch's oldest tracked date
establishes the tracking floor; subsequent runs process every eligible filing within that scope,
including late arrivals and backlogs larger than the initial `--per-company` value. Metadata
changes create immutable corrections. Initial empty snapshots retain the pilot start date.

The [SEC submissions API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
provides a recent window and links to additional historical JSON files. The collector fetches
listed historical pages overlapping the tracked range, with a budget of ten pages per company.
A budget failure, malformed page, unexpected URL, issuer mismatch or conflicting overlap cannot
advance the checkpoint. Archive-derived changes cite the actual archive capture/hash.

A missing accession inside covered dates becomes `missing_unconfirmed`. It is **not automatically
called withdrawn**. An accession rolling beyond observed coverage is reported as `uncovered`
and keeps its prior state. Empty or incomplete snapshots do not prove absence. A reappearing
accession restores the observed active state while preserving the intervening history.
The SEC documents that [post-acceptance removals and corrections](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
may appear in rebuilt indexes; absence in a recent page alone is insufficient proof of withdrawal.

Confirmed withdrawal/restoration is an explicit operator attestation:
`POST /api/v0/admin/development/versions/{version_id}/lifecycle`, requiring an admin token,
Idempotency-Key, expected_version, action (`withdrawn` or `restored`), a HTTPS SEC evidence_url
and a substantive reason. It records actor/time/citation without deleting the original event.
It is evidence supplied by an operator, not automatic verification of the linked page's content.
Only a confirmed withdrawal can be explicitly restored. Automated presence does not erase a
confirmed withdrawal, and unchanged metadata preserves a restoration's audit receipt.
No confirmed withdrawal was fabricated for the real pilot corpus; those flows use test data.

Feed projection now queries only unprojected versions for each owned issuer/thread, capped at
500 per thread per refresh. Repeat refresh for a larger backlog. Feed reads resolve the latest
canonical source status at the requested as-of and mark old cards as superseded, even before
new correction cards are projected. Historical cursors use their recorded watermark; public
sharing still excludes every development event. There is no notification or dispatcher call.

## Running and resuming

From the project root in PowerShell:

```powershell
$env:DATABASE_URL='sqlite:///rie-dev-feed.db'
$env:DEV_INFORMATIONAL_FEED='true'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m engine.development_feed --user-agent 'Narrative Research linhpm.vpub@gmail.com'
.venv/Scripts/python -m uvicorn engine.api:app --host 127.0.0.1 --port 8888 --no-access-log
```

The existing five-minute cache and rate/response-size limits remain. Collection is an explicit
command, not a scheduled job. Old notices are not re-dated to today. A different accession,
including a new amendment filing, remains a separate notice until an explicit evidence-backed
cross-accession relationship is implemented.

The development DB was backed up before migration. The original SEC review/synthetic databases
were not migrated in this milestone; migrate them to0007 before restarting with current code.
Their existing previews may still run older code. Do not use test DATABASE_URL values on these
stores. Token/cache/database files remain ignored by Git.

## Visual algorithm diagnostics

Open **http://127.0.0.1:8888/map**, or the map link from the feed. The public demo needs no token;
real private notices require the existing `secrets/development-feed-access-token.txt` token.
An operator token for lifecycle attestations is stored separately in ignored
`secrets/development-operator-access-token.txt`; it is not needed to view the map.
Tokens remain in page memory and are cleared on logout; late private responses are discarded.

- Select one of five companies and an as-of timestamp. The map shows candidate and eligible
  edges, signed arrows, directed two-hop paths, mechanisms, citations and unmet conditions.
- The company/metric association is drawn as a dotted connector and is not a causal edge.
- Select a driver and assumed increase/decrease to call the **existing server-side matcher**.
  A scenario is hypothetical and never writes events, approvals, scores or notifications.
- Relevance is the product of edge strengths with two-hop decay; confidence is the minimum
  heuristic edge confidence, not a calibrated probability. Conditional paths stay conditional.
  Materiality and stock-price impact remain UNKNOWN unless separately supported.
- The F021/N08 example uses the existing isolated synthetic graph and decision trace, marked
  as synthetic. Real graphs are never promoted using demo strength or synthetic approvals.
- Real filing metadata is shown separately with current lifecycle status. It does not invent
  directional financial observations from a filing headline. At present live seed edges remain
  candidates; therefore the live map correctly reports no eligible causal path.
- Snapshot eligibility badges use the same server-side temporal checks as matching. A demo
  trace is hidden before its availability. Seed topology is bundled for installed-wheel use.

APIs: GET `/api/v0/impact-map` (private snapshot), POST `/api/v0/impact-map/scenario` (private),
GET `/api/v0/impact-map/demo` and POST `/api/v0/impact-map/demo-scenario` (synthetic public demo).
All are bounded to registered nodes, five tickers and at most two hops.

## Validation and remaining work

Regression tests cover backlog, dedup/correction, concurrent checkpoints, archive rollover,
malformed/partial data, absence/reappearance, withdrawal/restore authorization and retries,
point-in-time invalidation, private ownership and genuine matcher outputs. Browser smoke covers
pan/zoom, direction reversal, F021, real-mode separation, mobile layout and logout races.

Next quality milestone: extract period/unit-consistent financial observations from actual SEC
or issuer disclosures, attach source spans, establish independently reviewed causal mechanisms,
and evaluate on a labeled holdout. This is needed to measure real impact accuracy; passing
software tests or demo confidence cannot establish it. Add explicit cross-accession amendment
links and finer collection metrics as the corpus grows. Production security findings are tracked
separately and do not block this private development scope.
