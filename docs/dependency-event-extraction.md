# Local structured extraction experiment

The previous regex gateway emitted zero events from the23exposed complete articles.
An optional local CPU dependency parser now proposes explicit subject/predicate/object
assertions, including active and passive voice, without an issuer or news-specific
phrase list. This is a separate review queue, not a replacement production matcher.

`engine.event_candidates export` uses the existing reviewed complete-body/source hash
and cutoff gates. It retains block-to-original-source spans and suppresses navigation,
related links and boilerplate through the existing body selector. `extract` operates
offline on the exported snapshot. Its output records input/code hashes, model files
and installed package versions. Revalidate current source status before any future
use: an exported queue does not track subsequent withdrawals or corrections.

## Run locally

Create an isolated environment inside ignored source-cache; do not modify the service
environment. Install pip26.3 and requirements-extraction.txt. spaCy3.8.11 and the
official en_core_web_sm3.8.0 wheel are pinned; the wheel URL includes its SHA256.
The full resolved local package list is retained with experiment artifacts.

```powershell
.venv/Scripts/python -m venv source-cache/nlp-runtime
source-cache/nlp-runtime/Scripts/python -m pip install pip==26.3
source-cache/nlp-runtime/Scripts/python -m pip install -r requirements-extraction.txt
.venv/Scripts/python -m engine.event_candidates export --input <selections.json> --articles <article-store> --output <new-input.json>
source-cache/nlp-runtime/Scripts/python -m engine.event_candidates extract --input <new-input.json> --output <new-queue.json>
source-cache/nlp-runtime/Scripts/python -m tests.model_extraction_smoke
```

Files are new-only. The default service/containers do not install or load the model.
CI runs a separate isolated model smoke job with synthetic text only. Package/model
downloads do not upload private article content. Runtime parsing needs no API/network.

## Meaning of output

- Exact source spans establish what text was selected, not that the semantic roles are correct.
- Explicit actor required: no subject inheritance across clauses or coreference resolution.
- Passive voice requires an explicit by-agent; unresolved predicates stay in the audit.
- Negation, modals/conditions, coordination and embedded/quoted assertions retain review flags.
  Flags are conservative sentence-wide cues; their absence does not mean a claim is verified.
- Future will/shall is PROPOSED, never committed. Past VBD without flags is REPORTED_ACTION,
  never verified operating. Other cases remain UNKNOWN. Phase extraction is incomplete.
- Context DATE/TIME/MONEY/PERCENT/QUANTITY tokens remain raw spans. They are not normalized
  periods, affected revenue or event duration. Subject can be a metric or place, not a company.
- All proposals require semantic/identity review; mechanism, strength and horizon UNKNOWN.
  No automatic graph match, canonical event, feed card or notification is created.

## Product scope algebra

`engine.product_scope` compares explicitly annotated sets of products, materials and
geographies plus process-node intervals, preserving open/closed boundaries. Both sides
must use the same vocabulary digest. Results: EXACT, NARROWER, BROADER, PARTIAL_OVERLAP,
DISJOINT, UNKNOWN. Missing dimensions are UNKNOWN, including missing on both sides.
An explicit disjoint dimension can rule out overlap despite other unknown dimensions.
Crossed dimensions (narrower product but broader geography) remain PARTIAL_OVERLAP.

ScopeAnnotation binds reviewer interpretation to a source text hash and exact quote.
It does not automatically infer aliases, validate semantics, renew profile source review,
or authorize a graph edge. Review vocabulary definitions and the originating relationship
separately. Scope relation is not financial impact strength or the affected exposure share.

Two local AMD annotations reuse source-backed TSMC<=7nm and GlobalFoundries>7nm
microprocessor/GPU wafer scopes. Geography is absent in the quoted scope and stays unknown;
do not infer factory geography from a company's headquarters. All facts/profiles unchanged.

## Measured diagnostic

Private root: source-cache/dependency-extraction-2026-11-24.23previously exposed articles,
964substantive blocks ->345syntax proposals across23documents;296proposals carry one or
more review flags.1224verb predicates lack accepted explicit roles. These are NOT1224missed
economic events. The345count includes descriptions, metrics and non-actionable statements.
The old regex and this extractor have different output definitions; counts are not a
precision/recall comparison. Zero canonical events and zero feed cards created.

No new blind cohort or independent accuracy labels were created.95focused regressions
passed;8synthetic actual-model cases passed. Optional environment audit found an old pip
version, fixed by upgrading to26.3. Final indexed-package audit reported no known issues;
en_core_web_sm is not indexed on PyPI and was skipped by the vulnerability database.
Its official release checksum was verified during installation, not a security audit.

## Next blind evaluation protocol

Freeze extractor/package/model/vocabulary and baseline hashes before collecting a new
cohort of50–100economic event clusters across the seven existing mechanism families,
with unrelated and near-miss controls. Exclude every prior exposed document hash and
economic-event cluster, including syndicated rewrites and amended versions. Keep issuer,
time period and event-cluster splits explicit; archive complete sources and publication time.

Two independent AI reviewers receive source-only packets, no predictions, rules, filenames
encoding labels or each other's judgments. They independently mark economic assertions,
actor/predicate/object spans, negation, attribution, phase, scope and UNKNOWN. Freeze labels
before joining predictions. Record agreement/disagreements and adjudication separately;
AI agreement is not human gold. Do not let the implementation agent fill missing gold.

Report candidate precision, supported-assertion recall and unmatched/abstained counts with
denominators; separate exact/overlap span scores, actor resolution, negation/attribution
errors, phase confusion and scope relation confusion. Include group-specific outcomes,
not only pooled agreement. Collect labels independently of extracted candidates so missed
assertions remain in the denominator. Any wrong affirmative promotion of negated/conditional
claims blocks feed integration; aggregate accuracy still requires an explicit acceptance review.
No production claim, strength calibration or push activation follows from parser smoke tests.

Official references:
[dependency parsing and linguistic annotations](https://spacy.io/usage/linguistic-features),
[model versioning](https://spacy.io/usage/models),
[pinned model release/checksum](https://github.com/explosion/spacy-models/releases/tag/en_core_web_sm-3.8.0).

## Final validation

CI45414558098 at96287e2 passed1030SQLite tests (136.71s),1030PostgreSQL tests (249.16s),8actual-model synthetic cases with exact actor/object assertions, dependency audits and migration/seed/replay/downgrade. Post-audit local queue-final.json reproduces the same345proposals/model hashes and records pip26.3. Frozen baseline, input/code hashes and all proposal source spans reverified. These checks do not establish market-news precision or recall.
