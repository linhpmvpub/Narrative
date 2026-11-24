# Frozen evaluation of current reading cards

Full-article freeze supports `--matcher feed_cards` to use the same substantive
HTML blocks, boilerplate suppression and sentence-local matching as `article_cards`.
The default `legacy_paragraph` is retained for compatibility; its historical results
must not be presented as current card accuracy. The freeze receipt names the matcher.
Source gates and notification eligibility are separate from semantic relevance.

```powershell
python -m engine.evaluation.article_relevance --matcher feed_cards --selections LOCAL_SELECTIONS --directory NEW_LOCAL_FREEZE --exclude-packet PRIOR_PACKET
```

Use the private reviewed profile registry and article archive via
`COMPANY_PROFILE_ROOT`, `NEWS_ARTICLE_DIR`, with `DEV_INFORMATIONAL_FEED=true`.
Repeat `--exclude-packet` for every previous cohort. Invalid prior receipts fail
closed. Keep the complete source captures, selections, predictions and labels under
ignored `source-cache/`. Freeze before requesting any independent labels.

Reviewers receive only full article text, scope/evidence and IDs, without literal
matching rules, predictions or traces. Two independent fresh AI contexts write
complete separate votes. Existing consensus keeps disagreements unresolved and
evaluation excludes unresolved pairs rather than treating them as negatives.
Report positive support per company, sample selection, disagreements and misses;
AI agreement is not human ground truth. A high score on a small curated cohort
does not satisfy production acceptance or demonstrate event-cluster independence.

Do not tune against this cohort and describe a replay as new independent validation.
Use new unseen articles for subsequent evaluation. Semantic overlap between reports
about the same project may survive URL/shingle exclusion and needs separate review.
