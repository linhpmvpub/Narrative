# Local full-article relevance evaluation

This experiment measures informational narrative relevance, not price prediction,
realized financial impact, push quality, or historical as-of accuracy. Real
notifications remain disabled. Research profiles are separate from the active feed.

## Source and evaluation pipeline

1. Select public documents independently of matcher predictions, including negative
   controls. Preserve failures such as HTTP 403; do not bypass them. Archive exact
   HTML and visible text through `engine.news_articles.capture` and retain hashes,
   observation time, publication date basis, and the exact URL. Manual observations
   are explicitly `MANUAL_PUBLIC_DOCUMENT_OBSERVATION_NOT_RSS`.
2. Review complete body boundaries against the archived source. Preserve substantive
   sections, qualifications, cautions and footnotes. Exclude site navigation/footer
   and author biography. Optional related-link removals must be exact two-line
   `Related:` blocks, with original text offsets retained. The operator declaration
   is not an automatic proof that a body is complete.
3. Version source-backed research profiles before freezing. Keep sector context
   distinct from company orders, named suppliers, and realized impact. Enabled
   factor bindings must have valid sourced routes to their explicit narratives.
4. Freeze with `python -m engine.evaluation.article_relevance --selections LOCAL_JSON
   --directory NEW_LOCAL_DIRECTORY --exclude-packet PRIOR_PACKET_JSON` (repeat the
   last option for every prior applicable packet). Set `DEV_INFORMATIONAL_FEED=true`,
   `COMPANY_PROFILE_ROOT` to the research registry, `NEWS_ARTICLE_DIR` to its article
   archive, and `SEND_NOTIFICATIONS=false`, `ALLOW_SYNTHETIC_LIVE=false`, `LLM_MODE=none`.
   The command rejects changed provenance, missing boundary review, future clocks,
   exposed URLs/near-duplicate text, and incomplete profile registries. It never
   rewrites an existing freeze directory.
5. Give two fresh-context AI reviewers only packet/receipt/readable copies. Keep
   predictions, rule bindings, traces and peer labels out of their instructions and
   reading scope. Require all IDs, hash, time and independence declarations. Labels
   are AI reference judgments, not human gold. Shared filesystem is not isolation.
6. Use `python -m engine.evaluation.profile_relevance consensus --directory LOCAL_DIR
   --review REVIEW_A --review REVIEW_B`, then its `evaluate` action with consensus
   labels. Evaluation rechecks captured bytes, body boundaries, selection and trace
   hashes. Disagreements remain unresolved, never silently counted as negatives.

## Interpretation and limitations

`full_article_relevance` is a separate track. It cannot satisfy the feed acceptance
gate and does not claim freshness eligibility. Old articles are read with current
profiles and source retrieval clocks; this is not a point-in-time backtest.

The matcher examines each visible-text line separately, including the headline.
It cannot assemble topic, context and activity from unrelated paragraphs or borrow
headline terms for the body. Exact offsets refer to the displayed reviewed body.
HTML inline elements may fragment sentences in this conservative normalization and
cause misses. Generic boilerplate/cautionary lists may still produce false matches;
independent reviewers must judge substantive developments, not repeated company text.

The November 24 cohort is a purposive sample of 15 documents/150 narrative pairs,
with four Sandisk releases, five AMD releases, three Dell articles, two industry
articles and one energy control. It is not a representative market sample or 150
independent events. The AMD target scope now explicitly permits conditional industry
component/power/cooling context, while excluding competitor-only launches. Any
previous-profile comparison uses these current targets and must disclose that scope
clarification. Do not pool its metrics with earlier RSS or freshness cohorts.

Raw sources, research profiles, full bodies, selections, frozen predictions, traces
and reviewer rationales stay in ignored `source-cache/`. Only code, synthetic tests,
documentation and aggregate results belong in GitHub. Active profiles and running
API/feed are not automatically promoted by an evaluation result.
