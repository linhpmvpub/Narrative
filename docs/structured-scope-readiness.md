# Identity-anchored scope readiness

`GroundingRule.identity_reference_id` optionally binds the actor to an existing exact
legal entity reference. Validation requires its current reviewed name, SOURCE_BACKED
status, upstream node, authorized relationship and review window. A name anywhere in
a shared quote cannot authorize a different supplier's edge. This is source-reviewed
identity within a profile, not global identity merging or independent causal proof.

Use `engine.structured_news --require-identity` for real-profile shadow runs. The default
retains legacy synthetic/name-only compatibility; such cards explicitly say
REVIEWER_DECLARED_NAME_ONLY. Strict runs reject unanchored rules rather than silently
routing them. Neither mode installs cards into the live feed.

Compound object phrases with and/or remain literal, bounded spans. They must match the
ENTIRE reviewed object. Coordinated actors/locations still abstain; a second action in
the object does not match a reviewed atomic object. This is not semantic paraphrase or
product taxonomy matching. Unsupported grammar remains a major coverage limitation.

Run a read-only readiness audit before collecting event predictions:

```
python -m engine.structured_scope --rules LOCAL_RULES.json --profiles LOCAL_PROFILES --output source-cache/NEW_READINESS.json
```

The audit checks source/profile pins, identities and reachable directed paths, reports
ready/held rules and narrative coverage per profile, and rejects registry changes.
Readiness is not extraction recall, relation completeness or financial-impact accuracy.

Current private rules:10, covering two explicitly identified AMD wafer suppliers across
five production actions. The complete source wording distinguishes <=7nm from >7nm
CPU/GPU wafers. No general supplier outage is automatically assigned to either process
scope. Rules were reviewed by AI_OPERATOR, reuse existing cached source evidence and
remain separate from active profiles. Other company scope mappings are still missing.

Fifty synthetic counterfactual probes passed (10scoped positives,40scope/actor/negation
negatives). They use real profile facts but fabricated event statements, NOT news.
On23previously exposed complete articles the new parser extracted0events;1571clauses
were unsupported. This result is deliberately preserved. No real-news accuracy gain
is claimed, and the old frozen predictions/labels were not changed or reused as holdout.

See codex/QUALITY_REVIEW.md for ranked remedies and acceptance gates. All detailed
sources/rules/probes/diagnostics remain in source-cache/structured-scope-2026-11-24.
The successor baseline pins the same atlas with the new runtime; the rule hash is
recorded separately in the manifest and aggregate report. Prior baselines are retained.
