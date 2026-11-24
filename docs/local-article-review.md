# Local article correction review

This operator workflow is local CLI tooling, not a remote admin page. Keep its
output under ignored `source-cache/`. No new API, cloud transfer or notifications
are enabled. Configure `DATABASE_URL` to the news inbox and `ARTICLE_FEED_ROOT`
to the existing local feed directory. The account database is not the inbox.

```powershell
python -m engine.article_review queue
python -m engine.article_review prepare --url EXACT_ARTICLE_URL --output source-cache/review-unique-id
```

The queue reports held states, changed/blocked inbox anchors and expired proof.
`RECHECK` means retry the ordinary source refresh, including temporary outages;
`EXPLICIT_BODY_REVIEW` requires examining the changed source. Queue classification
is operational triage, not a complete substitute for the feed's integrity gates.
Publisher withdrawal in the inbox blocks preparation; resolve it at the source
and collector before attempting a replacement. Never clear it merely to revive a card.

Preparation captures the allowlisted source again, retains the previous capture,
pins the entry and inbox versions, and writes:

- `review.html`: escaped, inert whole-visible-text diff, with no external resources.
- `candidate.txt`: normalized visible text for finding exact body offsets.
- `selection.json`: candidate with intentionally incomplete body review.
- `receipt.json`: pinned candidate identity and concurrency guards.

Read the complete candidate, not only the diff. In `selection.json`, edit only
`body_review`: zero-based character `start`/exclusive `end`, `complete_body:true`,
nonempty `reviewer_id` and `boundary_basis`, and an aware ISO `reviewed_at` after
the capture. Reassess any `related_link_ranges`; do not copy offsets blindly from
the old body. Character offsets refer to normalized text, not raw HTML bytes.
The receipt is a local operator artifact, not a cryptographic reviewer identity
or proof of independent human review. Keep it unmodified.

```powershell
python -m engine.article_review approve --output source-cache/review-unique-id
python -m engine.article_feed refresh
```

Approval rejects incomplete boundaries, altered candidates, stale entry snapshots
and changed inbox anchors. On conflict, prepare into a new directory and review
again. Approval only enters `AWAITING_RECHECK`; the source must still pass refresh
and all normal feed gates. Source text, article history and old review directories
remain local. An HTML withdrawal notice remains blocked by refresh even if an
operator supplied body boundaries. No approval asserts financial impact or causality.

The existing low-level `article_feed approve-replacement` command remains available
for operators; use this pinned packet workflow for concurrent review sessions.
