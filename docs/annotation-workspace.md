# Assigned annotation workspace and cross-source assessment

## Open and use

Open `/label` on the existing local preview (http://127.0.0.1:8888/label) or the approved email-restricted Cloudflare hostname saved in ignored secrets/mobile-preview.json. The original phone hostname is preserved while the tunnel runs. Use the existing member application token in secrets/development-feed-access-token.txt; never send that token in chat or put it in a URL. Cloudflare email OTP remains the outer gate; the app separately checks assignment and account identity.

The current member is assigned the frozen **204-case** packet (132 language,72 segment). Filter by company, case type and your own completion status. Open a case, read the cited source, select a judgment, add rationale and explicitly attest independent work. Numeric comparable cases require independently transcribed USD operands and period boundaries; uncertain/incomparable cases may omit operands and explain why. No model classification or computed numeric result is prefilled. Source fact/context locators and frozen hashes are available; raw captures remain in ignored source-cache/sec-review-2026-11-20. If the linked live document differs, use the frozen capture and report the discrepancy before labeling.

Saving creates a new immutable label revision. Your previous revision remains in the operator export. Same-request retry is idempotent; stale expected_version/hash returns409. Case switching warns about unsaved edits. Logout clears tokens and source text; late responses cannot restore them. Labels never approve graph edges or send alerts. The development DB currently contains **zero real labels**; all simulated browser submissions used intercepted synthetic API responses.

## Identity and blinding

Cases are imported with an exact content check against the source packet at its historical cutoff. Only blind fields are stored, not sealed predictions. Each account needs an explicit packet assignment; same tenant alone grants no access. Annotators can read only their own labels, never another account's labels or consensus feedback. The three source-group research assessments shown on the map are deliberately absent from the blind labeling UI.

The account ID is supplied by server authentication, not a form field. Separate account IDs plus an independence declaration are auditable controls, not proof that two different humans reviewed the material. The existing corpus was visible during development; future unseen periods are required before generalization claims.

A second genuine reviewer needs their own provisioned account. Operator provisioning is local; do not create pretend reviewers or auto-submit labels. The Cloudflare prototype currently allows only the user's approved email. Keep a second reviewer local or obtain authorization for their remote access; do not broaden the email gate silently.

## Operator commands and export

Schema head0010. Back up development DB before migration. Set DATABASE_URL=sqlite:///rie-dev-feed.db, DEV_INFORMATIONAL_FEED=true, SEND_NOTIFICATIONS=false, ALLOW_SYNTHETIC_LIVE=false, LLM_MODE=none.

```powershell
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m engine.annotations --blind-cases source-cache/evaluation-segments-v1/blind-cases.json --user-id ACCOUNT_ID
.venv/Scripts/python -m engine.corroboration --file reports/cross-source-assessment.json --captures source-cache/corroboration-2026-11-21
```

Import is idempotent and assigns zero labels. Use the same import with another genuine account ID to grant access to the same packet. Assignment is explicit; no public registration or role selection was added.

Global operator only: GET `/api/v0/annotations/{packet_id}/export` on loopback. Export contains all immutable revisions, latest revision per reviewer/case and `holdout_language_labels` compatible with `engine.evaluation.filing_labels.evaluate(sealed_packet, labels)`. Only current-source holdout language cases are included in that evaluation list. Development, numeric and inactive/superseded cases are reported separately. Numeric labels remain available for separate human adjudication. Never export the sealed predictions to the annotator or commit human labels/tokens/raw case packets.

The evaluator requires two agreeing independent reviewer declarations and leaves disagreements pending; neither labels nor source assessments change production matching. Numeric consensus/adjudication and genuine causal-effect estimation are still pending workflows.

## Source changes and transport

Labels record source_sha256 and server review time. Latest source status/identity and filing snapshot version are rechecked before saving under the shared database-mode lock. Withdrawn, changed or superseded cases remain inspectable but reject new submissions. Existing labels retain their history; export excludes invalidated evidence from current evaluation. A replacement packet requires an explicit new source-consistent import.

Mobile gateway remains read-only for feed/account/graph management. Its only new write exception is POST `/api/v0/annotations/{64-hex-packet}/cases/{64-hex-case}/labels`, requiring normal app authentication, assignment, idempotency and revision validation. Idempotency-Key is forwarded. Admin/export routes remain blocked, as are unlisted mutations. No server-side token injection, no automatic source acquisition per page view. Both services remain loopback; Cloudflare's approved email restriction is retained.

## Cross-source research result

Five captured documents from **three publisher groups** (TrendForce, Microsoft, HPE), not five independent votes. Full metadata, short excerpts, source hashes and eight relationship assessments are in reports/cross-source-assessment.json. Data availability starts at actual ingestion time; historical as-of cannot see newly collected evidence. Immutable assessment versions support replacement and A→B→A restoration; no silent graph approvals.

| Relationship | Result | Remaining evidence |
|---|---|---|
| R006, DRAM price → MU revenue | Partial industry corroboration | Separate price, volume, mix and fiscal/calendar timing |
| R005, DRAM price → MU margin | Insufficient company margin evidence | Unit costs, yield and technology transition |
| R010, accelerator demand → NVDA revenue | Customer demand context | NVIDIA allocation, actual deliveries and revenue timing |
| R017, Instinct shipments → AMD revenue | Product availability corroboration | Shipments, prices and period revenue |
| R019, EPYC adoption → AMD revenue | Product availability corroboration | Incremental deployments and revenue by generation/period |
| R028, pass-through → Dell ISG margin | Peer mechanism only | Dell-specific pricing and contractual evidence |
| R024, Dell AI revenue → ISG margin | Insufficient direct external evidence | Product margin and mix bridge |
| R027, component costs → Dell ISG margin | Unconditional inference challenged | Whether cost is offset, timing and pass-through |

Sources: [TrendForce industry research](https://www.trendforce.com/presscenter/news/20260907-13219.html), [Microsoft earnings call](https://www.microsoft.com/en-us/investor/events/fy-2027/earnings-fy-2027-q1), [Azure EPYC options](https://learn.microsoft.com/en-us/azure/confidential-computing/virtual-machine-options), [Azure Instinct configuration](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ndmi300xv5-series), [HPE earnings call](https://investors.hpe.com/~/media/Files/H/HP-Enterprise-IR/documents/q1-2026/hpe-q1-26-earnings-transcript.pdf). Microsoft is a commercial customer/partner and HPE a peer competitor; their statements are not neutral experiments. A Community Hub article was readable through web search but direct snapshot acquisition returned403, so archived Microsoft Learn documentation was used instead.

Conclusion: external sources refine mechanisms and counterconditions, but **zero edges receive independent human approval or identified causal effect sizes** in this pass. Stock-price impact remains UNKNOWN. Next: genuine independent annotations and adjudication, company-specific corroboration/counterevidence and unseen-period evaluation.
