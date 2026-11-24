# Structured event grounding: local shadow v1

This optional pipeline extracts candidate actor/action/object/location records from
reviewed article bodies, matches an explicitly reviewed source-backed scope, and
then traverses existing profile relationships to a narrative. It does not invoke the
legacy bag-of-terms bindings as fallback. It does not change the live feed.

The first implementation deliberately supports a narrow English clause grammar:

- `Alpha Foundry plans to build wafer factories in Texas.` -> PROPOSED capacity UP.
- `Alpha Foundry built wafer factories in Texas.` -> REPORTED_ACTION, not verified operation.
- Other action families cover production halt/resumption, orders, prices, funding,
  licenses and sampling. These are action types, not demonstrated coverage rates.

The parser preserves exact actor/action/object/location spans in the reconstructed
source block and the block's original HTML text spans. Missing geography stays absent.
It does not resolve pronouns, merge sentences, infer occurrence time, interpret
complex coordinated clauses, or estimate a financial effect. Negation, attribution,
conditional language and unsupported syntax abstain. Metaphorical objects cannot
match an exact reviewed object. Reported action direction is not narrative stance.
No source refresh or real-time publisher truth is claimed by capture integrity.

## Reviewed grounding contract

`GroundingRule` pins profile ID/hash, one anchoring relationship, actor, object,
optional exact geography, canonical action, source ID and a quote from that
relationship's evidence, version and a named HUMAN/AI_OPERATOR reviewer. Scope names
must occur as whole terms in the cited quote. Review is bounded to at most90days;
unknown profiles, changed profile hashes, future/expired reviews and unsubstantiated
scope fail closed. Status can be revoked/disputed. This validates provenance, not
whether the reviewer interpreted the source correctly; a name match is not global
legal-entity resolution or independent causal approval.

The full registry is read through existing source/hash checks before and after the
run. Candidate routing requires a current source-backed anchoring relationship;
the resulting directed path must actually contain that relationship. Conflicting
anchors within a profile, truncated paths, absent/mismatched scope and revoked
relations yield no candidate. Existing structural membership and path limits apply.
Financial overlays and segment revenue shares do not become causal paths/weights.

Every candidate retains source packet/selection hash, rule/profile hash, event fields,
relationship evidence, UNKNOWN financial magnitude/horizon and review blockers.
Unmatched/unsupported clauses retain audit reasons. Duplicate selection inputs are
idempotent within a run. Output is bounded; overflowing batches fail instead of
silently presenting incomplete results. Delivery is always disabled.

## Local command

```
python -m engine.structured_news --selections LOCAL_SELECTIONS.json --rules LOCAL_RULES.json --profiles LOCAL_PROFILES --articles LOCAL_ARTICLES --output source-cache/NEW_RESULT.json
```

Use the existing complete-body selection/capture workflow and
`DEV_INFORMATIONAL_FEED=true`. Output must be a new file. Keep inputs and detailed
outputs under ignored source-cache. This CLI is a shadow diagnostic: no API/feed
installation, canonical ingestion, new network endpoint, subscription or dispatch.

## Current evidence and next work

The local synthetic demo completes source capture -> reviewed body -> typed event ->
reviewed scope -> two-edge narrative path -> one candidate card. All names and market
claims in that demo are synthetic, not a real investment example. Real grounding
rules populated in this iteration:0. No improvement in real-news recall is claimed.

The previous23article/230pair pilot remains frozen and exposed; it is not rerun as a
new holdout. Its old baseline files are preserved. A successor local baseline records
the same atlas with the new runtime; its pin is in the checkpoint/aggregate report.
The old baseline's current-runtime verification should now fail, as designed: use
its original commit for replay, never overwrite its fingerprint.

Next: populate reusable reviewed entity/product/geography scope mappings from the
company database, broaden extraction against a declared grammar/ontology specification
(including mixed phases and quantity/time spans), and run a new independently labelled
holdout. Record unsupported coverage and unresolved scope, not just precision on
selected candidates. Preserve separate industry-context and verified-company exposure
labels. Financial strength/horizon calibration and live push remain pending.

## Validation

71 focused regressions passed, including49 new structured-event tests. After the
immediate output-bound guard, all49 structured tests passed again. Fresh CLI output
matched the synthetic integration artifact exactly; a500rule/3clause stress batch
failed closed at the candidate limit. Ruff and mypy131files passed.

CI45406267040 on0251891be305c71127888f261ef19fa31dfefef9 passed993SQLite tests
(125.63s) and993PostgreSQL tests(209.65s), dependency audits, JavaScript syntax and
migration/seed/replay/downgrade. These are software regressions, not a blind news
accuracy score. Final baseline is evaluation-baseline-v2; the first successor remains
preserved as superseded after the output-bound change.
