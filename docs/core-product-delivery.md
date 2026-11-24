# Core product delivery

The product surfaces news investors might miss and explains its relationship to a
company or a chosen narrative. It does not predict share prices. Priority is an
auditable reading experience: source excerpt, relevant factor, sourced path,
narrative, uncertainty, and publication time.

## Implemented local reading loop

`python -m engine.article_cards --selections LOCAL_SELECTIONS --output NEW_LOCAL_DIR`
builds `cards.json` and a self-contained `index.html`. Use the research profile and
article archive environment variables documented in full-article-relevance.md.
No server, account, external scripts, analytics or cloud upload is required.
The HTML works at desktop and mobile widths, but a local computer file is not a
remote phone URL. It does not replace the active API/feed or enable notifications.

The builder rechecks source hashes and reviewed boundaries. It reconstructs
inline HTML fragments within structural blocks, retaining source text offsets.
It never combines keyword groups across sentences, headlines and body paragraphs.
Company boilerplate, cautionary appendices and certain measurement qualifications
are withheld from matching; the full source remains archived. This conservative
filter can lose useful information after an appendix heading. It is not a general
semantic novelty detector.

Cards show literal source excerpts rather than generated financial claims, paths
and their profile citations, unknowns, profile version, and source links. Company
name mention is distinguished from industry context and does not prove exposure.
Fresh-window cards sort first; historical context is visibly marked and can be
hidden. Passing freshness alone is not feed acceptance or delivery permission.

## Next implementation order

1. Make the local reading loop useful on the existing feed: opt-in reviewed article
   queue, correction/withdrawal revalidation, company/narrative filtering and clear
   evidence disclosure. Keep industry context separate from confirmed exposure.
2. Improve concrete gaps in five company profiles, beginning with flash storage
   demand and deployment constraints. Expand source-backed factors when a real
   missed story demonstrates the need, rather than adding broad ticker shortcuts.
3. Use a bounded new blind sample to check regression and precision before promotion.
   Keep historical examples for debugging and explanation, not as fresh validation.
4. Add personal narrative selection, relevance ranking and feedback to the reading
   loop, then operational validation. Enable actual push only in a later explicitly
   approved release once deduplication, corrections and evidence gates are met.

The November 24 development replay is exposed-label tuning, not a new holdout:
TP21/FP2/TN107/FN7/unresolved13 versus the prior frozen TP23/FP12/TN97/FN5. Lower
noise trades off some recall. No production precision or launch acceptance claim.
