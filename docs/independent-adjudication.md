# Two-reviewer consensus and independent adjudication

## Use the workflow

1. Two genuine reviewers use separate assigned member accounts at `/label`. Each reads the source, transcribes comparable USD operands and periods where applicable, provides rationale and declares independence. Neither sees model output or the other reviewer's labels. The current campaign has two assigned reviewer slots and one packet-scoped adjudicator; see [campaign guide](campaign-204-guide-vi.md). do not create fake people or machine-generated human labels. A second reviewer can work locally; the approved Cloudflare email restriction remains unchanged.
2. Open **http://127.0.0.1:8888/adjudicate** on the host computer. Use the existing operator credential from ignored `secrets/development-operator-access-token.txt`. Keep it out of URLs, screenshots and chat. This page and its API are deliberately unavailable through the phone gateway.
3. The default queue shows disagreements and deferred cases. Read the source and the latest votes. A third assigned adjudicator account (or global operator), distinct from every annotator on that case, can resolve with a language label or independently transcribed numeric comparison, or defer without creating a reference label. A reason and independence declaration are mandatory. No model answer is shown or preselected.
4. Refresh the report to see reference-label coverage, raw pair agreement, holdout classification accuracy and exact numeric comparison accuracy. The denominator remains the full frozen holdout, including pending and invalid-source cases. Null accuracy means no eligible scored labels; it is not zero accuracy.

Notifications remain disabled. Consensus and adjudication never approve relationships, alter the feed/graph or create alerts.

## Consensus, versions and conflicts

Only the latest revision from each distinct account counts. Two or more current independent votes must all agree; a third conflicting vote prevents consensus, even if two agree. Language classes must match exactly. Numeric comparable labels must match USD unit, both values and all four period boundaries. Decimal formatting differences such as `120` and `120.0` are equivalent, but significant digits are never rounded away. Non-comparable/uncertain labels compare their verdict; optional operands do not turn them into comparable references.

Each adjudication appends an immutable revision, preserving original labels and earlier decisions. Its fingerprint binds the source hash/status and the IDs/versions of all current votes. Any new or edited vote invalidates an earlier adjudication; source inactivity, replacement or supersession excludes the case. Expected vote fingerprint and decision version prevent stale writes; an idempotency key makes exact retries safe. Self-adjudication returns403. Insufficient votes, consensus-only cases and stale input return409. Deferred cases have no reference label and cannot improve the reported score.

Separate accounts plus declarations are auditable controls, not proof of different human identities. Assign annotators member roles and keep the operator separate. Operators have cross-review access for adjudication/export; they should not work as blind annotators on those cases.

## Frozen predictions and reproducibility

Migration **0012** adds packet-scoped campaign participants; migration **0011** stores immutable predictions and adjudication revisions. Predictions must be frozen before any labels exist. The import verifies the exact original source-derived packet and predictions at the stored cutoff; changed predictions or a freeze after label collection are rejected. An identical retry is idempotent. Predictions are never returned by annotator endpoints or the adjudication case detail.

```powershell
$env:DATABASE_URL='sqlite:///rie-dev-feed.db'
$env:DEV_INFORMATIONAL_FEED='true'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m engine.evaluation.consensus --freeze source-cache/evaluation-segments-v1/sealed-predictions.json
.venv/Scripts/python -m engine.evaluation.consensus --report-packet 526bd6298883375e06874ca83a78069104f1411ad5e103455f0c357d5b70ac9f
```

Back up before migration. Raw packets, captures, labels and credentials stay ignored. Store any human-label export under ignored source-cache, never in the public repository.

Local admin API prefix `/api/v0/admin/evaluation`:

- GET `/packets`, `/{packet}/cases`, `/{packet}/cases/{case}`: packet queue and source/vote details.
- POST `/{packet}/cases/{case}/adjudications`: revision-bound resolved/deferred decision.
- GET `/{packet}/quality`: aggregate metrics, prediction SHA256/freeze time, input fingerprint and coverage.
- GET `/{packet}/export`: current states/reference labels plus all label/adjudication revisions and quality report. No raw model predictions. Preserve this private export alongside the original sealed packet for an audit; the live report recalculates against current source eligibility.

The legacy annotation export remains a raw-label export. Use the new evaluation export/report for adjudicated reference labels and numeric scoring.

## Interpretation and current state

The actual packet has **204 cases:132 language and72 segment comparisons**. AMD/SNDK form issuer-held-out evaluation: **60 language and15 numeric cases**. Remaining cases are development examples and are excluded from accuracy. All available latest reviewer pairs contribute to descriptive raw agreement, before adjudication; with more than two reviewers the statistic is pair-weighted. Language confusion matrices have gold rows and prediction columns. Numeric scoring is exact-match across the full comparable tuple; a model comparison labeled uncertain/non-comparable counts as incorrect, not silently excluded.

The real predictions were frozen while labels were still empty. `reports/adjudication-pending-quality.json` records **0 real labels,0 adjudications,0 alerts**, accuracy null, coverage0. Browser writes were intercepted synthetic tests only.

These metrics do not establish stock-price prediction accuracy or causal effect sizes. Numeric cases include extracted positives only, so they cannot measure extraction recall. The corpus was visible during development; even complete consensus is not evidence of generalization to unseen periods. Pending disagreements can bias conditional accuracy, so inspect coverage and source exclusions with the score.

Next: obtain two actual independent reviews and third-person conflict resolutions, analyze errors by issuer/class/period, then repeat with unseen filings and manually sampled missing/negative numeric cases. Real graph approval still requires separately verified causal evidence.
