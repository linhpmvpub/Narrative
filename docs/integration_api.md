# Standalone integration contract — P4

Base path `/api/v0`; OpenAPI `/openapi.json`; Swagger `/docs`. Readiness requires migration **0004**. Live delivery remains disabled. Threadnote application/identity-provider integration is pending.

## Authentication and writes

Provision with `python -m engine.api.accounts --tenant local-demo`. The command prints an opaque bearer token once; its SHA256 hash, 30-day expiry and revocation state are stored in `rie_tokens`. Set `revoked=true` to revoke. There is no public registration. `--admin` explicitly creates a **global operator**, not a tenant administrator. Never expose operator tokens in a frontend.

Private routes resolve identity, tenant and role from the token database. Resources belong to an exact user, including within a tenant. Foreign and missing resources both return 404. Legacy `API_TOKEN` grants catalog access only. Provisioned tokens also work for catalogs; custom drafts never appear there.

Mutating user routes and relationship review require `Idempotency-Key` (1–128 characters). Same user/route/key/body returns the committed receipt; changed body returns 409. User locks serialize quota checks and feedback replacement. Mutation and receipt commit atomically. Admin replay uses content/as-of identities and immutable projection keys instead; retrying completes partial projections without duplicate cards.

Errors contain `code`, `message`, `request_id`; validation includes field locations without echoing input. Authentication: 401; member/operator mismatch: 403; missing/foreign resource: 404; version/quota/idempotency conflict: 409; invalid scope: 422; database unavailable: 503.

The security boundary limits each request body to 65,536 bytes before JSON parsing, including bodies without Content-Length. Oversize requests return 413; malformed/duplicate/mismatched lengths return 400. API responses through this boundary include `Cache-Control: no-store`, `Referrer-Policy: no-referrer` and `X-Content-Type-Options: nosniff`, including private data and public share previews. A shared URL remains a bearer capability: redact it from logs. These controls do not replace ingress time/rate/concurrency limits.

## Routes

| Route | Access | Behavior |
|---|---|---|
| GET `/stocks`, `/narratives/templates` | Catalog token or account | Five stocks, ten templates; identity verification pending |
| POST `/narratives` | Account | Compile immutable draft v1 |
| PUT `/narratives/{id}` | Owner | Append draft; requires `expected_version` |
| POST `/narratives/{id}/approve` | Owner | `confirmed:true`, `expected_version`; append approved version |
| GET / POST `/subscriptions` | Account | List active / subscribe after confirmation |
| DELETE `/subscriptions/{id}` | Owner | Soft disable, retaining readable history |
| GET `/threads/{id}/feed`, `/threads/{id}/story` | Owner | Chronological cards, traces, correction links, reported observations |
| POST `/alerts/{id}/feedback` | Card owner | Append feedback; WRONG opens quality review |
| POST `/threads/{id}/sharing` | Owner | `is_public:true` returns bearer link; false revokes |
| GET `/public/stories/{token}` | Bearer-link possession | Redacted factual preview, max 100 entries |
| POST `/admin/fixtures/replay` | Global operator | `demo:true`, aware `as_of`; offline replay and projection |
| POST `/admin/relations/{id}/review` | Global operator | Evidence-backed approval or audited rejection |
| GET `/admin/review-queue` | Global operator | Open reviews, bounded limit |
| GET `/admin/eval-report` | Global operator | Synthetic baseline; historical evaluation pending |

Subscription example: `{"thread_kind":"narrative","target_id":"N08","confirmed":true}` or `{"thread_kind":"stock","target_id":"CO_DELL","confirmed":true}`. Free tier: 3 active stocks, 1 active narrative. Custom narratives require ownership and approval. Template confirmation never changes global graph verification.

Narrative input requires `primary_ticker`, `title`, `thesis`, `horizon_months` (1–60), 1–3 distinct registered `driver_ids`, `supporting_evidence`, `challenging_evidence`, `disconfirmation`, explicit `outcomes` (company metric to +1/-1), `hypothesis_polarity` (favorable/adverse), `max_hops` (0–2). Scope is enforced during evaluation. Text is user input, not a verified claim; no LLM guesses signs. Limit: 50 stored custom narratives per owner. Approval appends a version: draft v1 becomes approved v2. Edits append a draft, pausing new evaluation until approval, and never rewrite prior cards.

Feedback labels: USEFUL, ALREADY_KNEW, NOT_RELEVANT, UNCLEAR, WRONG; optional bounded `reason`. Prior feedback remains inactive in history. USEFUL/NOT_RELEVANT change only the personal relevance indicator; chronological history is not reordered. WRONG opens a quality-review reference. Source truth/confidence never changes automatically.

Relation review requires `action` approve/reject and nonblank `reason`. Approval also requires approved non-synthetic `evidence_ids`, `routing_basis`, bounded `strength`/`confidence`, optional aware `valid_from`, and `conditions`. Reviewer and review/recording time are server-controlled. P1 evidence checks and mandatory cost conditions still apply.

## Time, projection and privacy

Feeds accept aware `as_of`, `limit` (1–100), and `cursor`. Repeat the returned `as_of` on subsequent pages. Keyset cursors bind thread/cutoff and retain a projection-recorded cutoff. Order is source availability plus card ID; decision availability is separately filtered. An October source evaluated November 1 does not appear as an October decision. Synthetic templates use explicitly simulated time; custom versions retain actual approval time and cannot influence earlier replay.

One user/canonical event version has one card ID across matching threads. Per-thread explanations are immutable snapshots. Stock threads choose the first eligible template in deterministic narrative-ID order. New subscriptions can gain links without another card/delivery. Corrections append linked cards even when quality is unknown, provided the prior card was relevant to that thread; previous entries remain intact.

Financial observations are discrete reported values with citations and all source clocks checked. No interpolation or invented prices. Fixtures contain no approved financial series: observation list empty, `price_series:unavailable`.

Replay gathers all active threads per user before calling the P3 dry-run planner with kill switch enabled. No background scheduler or provider is installed. Fixture materiality remains unknown: qualified review/story entries, zero push/digest plans and zero sent alerts. Production source-to-feed projection awaits approved real inputs. Admin fixture replay refuses databases not explicitly initialized as synthetic.

Stories are private by default. Sharing rotates a revocable bearer link. Public allowlist includes source facts, synthetic labels, citation URLs, source times and correction flag. It excludes user/tenant/thread IDs, feedback, hypotheses, monitoring conditions, preferences and traces. This is a bounded preview, not full export. Revoke with a new idempotency key; retrying an old receipt cannot reactivate a revoked link.

Migration 0004 adds product tables without altering frozen P1–P3 schemas; synthetic decisions stay isolated from production narrative versions. Replay is synchronous and bounded to fixtures. Internet deployment needs P5 threat review, infrastructure rate limiting, real identity-provider integration and PostgreSQL runtime validation. No remote CI run or production readiness is claimed.
