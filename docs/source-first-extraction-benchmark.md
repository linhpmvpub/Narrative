# Source-first extraction benchmark

`engine.evaluation.extraction_benchmark` locks selected source passages and predictions,
exports a whitelisted source-only blind packet, validates independent label spans and
scores each reviewer separately. It does not manufacture consensus gold from agreement.

## Operator workflow

1. Declare source universe, deterministic selection, failed-capture policy, scope and
   prior-exposure screening before viewing predictions. Archive source bodies and dates.
2. Review passage boundaries and preserve the transformation/source offsets. Passage
   evaluation must not be described as full-article or independent-event-cluster coverage.
3. Run the pinned extractor and record input/code/model/package hashes. Freeze sources,
   predictions and protocol with a separately recorded receipt digest. Old files are never overwritten.
4. Give two independent AI reviewers only separate copies of blind.json and identical
   instructions. The packet whitelists id/text/title/source_url/published_at; private fields
   and predictions are excluded. Directory separation is an operational convention,
   not OS-enforced access control. Review agents must not inspect the frozen/private folder.
5. Reviewers mark all economic assertions in each source passage, including ones not
   extracted. Preserve forecasts, conditions, negation and uncertainty. Labels are not human gold.
6. Validate full case coverage, unique predicate anchors, original spans and label categories.
   Freeze returned label digests and evaluate against the original prediction receipt.
   Review disagreements separately; never replace either original label set to improve scores.

```powershell
.venv/Scripts/python -m engine.evaluation.extraction_benchmark freeze --cases <cases.json> --predictions <predictions.json> --protocol <protocol.json> --excluded-text-hashes <prior-hashes.json> --output <new-directory>
.venv/Scripts/python -m engine.evaluation.extraction_benchmark evaluate --root <frozen-directory> --pin <receipt-digest> --label-a <review-a/labels.json> --label-b <review-b/labels.json> --output <new-result.json>
```

The freeze API accepts already source-reviewed cases; it does not crawl, verify an issuer
claim, infer article completeness or establish semantic independence of event clusters.
Exact passage hashes reject repeats. Near-duplicate and semantic-event screening are
additional operator responsibilities and must be reported with their actual coverage.

## Label contract

Each reviewer provides reviewer_id, reviewer_kind=AI_INDEPENDENT and a complete cases list.
Each case has id, status=REVIEWED/UNSURE, assertions and comment. Each assertion contains
actor/predicate/object source spans, polarity=AFFIRMED/NEGATED/CONDITIONAL/UNKNOWN,
phase=REPORTED_ACTION/PROPOSED/UNKNOWN and attributed=YES/NO/UNKNOWN. Actor/object may be
null when not explicit. Predicate is one original lexical verb token; a copula can be used
for an economically meaningful measured state lacking a lexical verb. Do not label both
"forecast" and the economic predicate inside its reported proposition as the same claim.
Generic definitions, tool descriptions and boilerplate are not economic assertions.

The reporting agent is not an adjudicator. Different interpretations/role boundaries are
retained, and independence relies on separate source-only agent contexts, not proof of
independent training. Same-model AI reviewers can share errors and systematic biases.

## Metrics and limits

Exact predicate anchors determine diagnostic TP/FP/FN. One predicted anchor can match
at most one source-labelled assertion; duplicates count as extra proposals. Source-labelled
assertions without predictions stay in the recall denominator. UNSURE cases are excluded
explicitly, with counts, and empty denominators are null rather than a fabricated score.

Actor/object/phase exact counts are reported only over matched predicates. Null gold
objects are separately counted because an extractor requiring a direct object may miss
economic changes such as "prices fell". Negation/condition/attribution flag coverage is
reported over matched labelled assertions only; it is not whole-corpus recall and does
not measure affirmative impact promotion. All syntax proposals still require review.

Exact spans penalize different predicate or phrase boundaries even when meanings are
similar. These scores are not adjudicated semantic accuracy, relationship relevance,
financial effect, calibrated strength, duration, user usefulness or production acceptance.

## First wave: energy lead passages

Predeclared EIA2022January–November universe. URLs already present in local JSON artifacts
were excluded;224eligible entries were ordered by SHA256 of a fixed prefix+URL and the
first50selected before predictions.49captured successfully; one invalid-UTF8source was
held without replacement. Current source capture is not proof of historical availability.
First narrative paragraph >=180visible characters per article, excluding Source/Note/
Principal/From December prefixes, was selected by the same rule and reviewed as a passage.
Full captured HTML and context remain local; the benchmark labels only the chosen paragraph.

No selected passage met the >=80% containment threshold of its8word shingles in any of
383previously archived text files. This and URL exclusion do not prove economic-event
independence. Some documents concern the same macro trend. Report49documents/passages,
not49independent clusters; no bootstrap confidence intervals assuming independence.
This source/year/lead-paragraph sample is not the planned50–100diverse-event-cluster
benchmark and does not cover all seven mechanism families or company relationship quality.

Local root: source-cache/extraction-blind-2026-11-24. Source documents, predictions, labels,
per-case disagreements and detailed results remain ignored; publish aggregate counts only.
Predictions were locked before two source-only reviewers began. The extractor was not
changed or tuned on this cohort. Once scored, treat this cohort as exposed thereafter.

## First-wave results

Two independent source-only AI reviewers completed49cases. A marked160assertions with
2UNSURE cases (156assertions scored); B marked168 with none unsure. Predictions were
locked before review and the extractor was unchanged after seeing these sources.

| Reference | Scored proposals | Source assertions | TP / FP / FN | Exact-anchor precision | Exact-anchor recall |
| --- | ---: | ---: | --- | ---: | ---: |
| AI A,47reviewed cases |65|156|44 /21 /112|67.69%|28.21%|
| AI B,49reviewed cases |68|168|46 /22 /122|67.65%|27.38%|

Shared160predicate anchors,8additional for B.24cases agree completely;25require adjudication.
Across shared anchors,13actor and13object spans differ, plus2attribution and1phase labels.
The source-only adjudication queue is local; no original labels were edited and no consensus
gold was created. Low exact-case agreement is not the same as disagreement on every event.

Null-object source assertions matched0/26(A) and2/33(B). Phase exact12/44(A),13/46(B) only
among matched predicates. These measurements motivate generic intransitive/state extraction
and attribution/phase improvements, not story-specific keyword tuning. Hold this now-exposed
cohort for regression; judge improvements using a new disjoint source-first cohort.

Exposure qualification: "new" means not detected in the screened local project artifacts. It does not prove that public historical articles were absent from the pretrained reviewers' training data. Same-model reviewers may share biases; independent contexts are not independent training.

## Validation

52focused tests passed4.21s; final18benchmark tests passed0.23s. Ruff passed and mypy135files passed. CI45423957149 at438b687:1048SQLite tests148.14s,1048PostgreSQL tests283.86s,8actual-model synthetic cases, dependency audit and migration/seed/replay/downgrade passed. Source/prediction receipt, blind packet copies, independent label digests and final runtime baseline reverified; original extractor unchanged.
