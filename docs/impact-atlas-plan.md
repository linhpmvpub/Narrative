# Database-first relationship and impact development

## A. Data foundation — implemented

`engine.impact_atlas` builds a new immutable local SQLite/JSON/HTML snapshot from a
complete integrity-checked profile registry. SQLite stores profiles, nodes, relations,
sources, evidence, components, narratives, exposures, reviewed exposure facts and
the mechanism catalog. Foreign keys bind evidence and identities; profile IDs namespace
nodes so similar names never silently merge. Each snapshot has hashes and an explicit
cutoff. Existing source files/profile versions remain the evidence authority.

The schema is `IMPACT_ATLAS_V1`, separate from the API account database. This does
not migrate or replace canonical graph approval, subscriptions or existing feeds.
Build a new output directory for each version; do not edit an old snapshot or its
manifest. Interrupted exports without a complete manifest are unusable. `verify`
checks artifact integrity, not current publisher availability or source revocation.
Rebuild from the current validated registry after profile changes/revocations. The
static HTML is an archival research inspector, not a live feed or historical replay.

```powershell
$env:DEV_INFORMATIONAL_FEED='true'
$env:SEND_NOTIFICATIONS='false'
$env:ALLOW_SYNTHETIC_LIVE='false'
$env:LLM_MODE='none'
python -m engine.impact_atlas build --profiles LOCAL_PROFILE_ROOT --facts LOCAL_FACTS_JSON --output source-cache/NEW_ATLAS
python -m engine.impact_atlas verify --output source-cache/NEW_ATLAS
```

`--facts` is optional. Missing dimensions are UNKNOWN, never zero or low exposure.
`ExposureFact` requires relation identity, dimension, unit, scope, validity, knowledge
and review times, reviewer kind and exact source quotes from the same profile.
Fractions must be 0..1; day values must be finite/nonnegative. Qualitative concentration
has its own field: “substantially all” must not become an invented percentage.
Conflicting simultaneous facts are rejected, not resolved by insertion order. A
reviewer declaration and exact quote do not independently prove the interpretation
or causal applicability. AI_OPERATOR remains distinct from HUMAN.

## B. Five-company population — in progress, measurable gaps

The initial local atlas imports six existing research profiles for MU/NVDA/AMD/DELL/
SNDK, including a separate historical NVIDIA profile. All 42 component statuses
remain visible, with seven cross-company coverage groups. Unquantified relationship
context is not renamed as quantified economic exposure. Existing 49 nodes/55 relations
are a starting inventory, not comprehensive market coverage. No cross-profile entity
resolution is asserted. The first three reviewed facts cover narrow AMD wafer sourcing
and qualitative Sandisk wafer concentration, not total company revenue at risk.

Complete identity/products/revenue, supply/capacity, demand/customers, prices/contracts,
funding/financials, technology/competition and geography/hazards from sourced evidence.
Prioritize scope, denominators, substitutes, inventories and contract timing over
adding more unqualified graph edges. Some fields may be genuinely undisclosed; record
that only when supported, and preserve uncertainty in downstream assessment.

## C. Mechanisms and event frames — foundation implemented

Seven reusable mechanisms describe disruption, input price, capacity, demand,
technology, financing and policy. Each declares its input driver, immediate conditional
channel, necessary conditions and mitigating dimensions. The generic sign concerns
that channel only; it is not propagated into company margin, revenue or share price.
The same event may have competing pathways. No fixed relationship strength is inferred.

`engine.impact_events` accepts a reviewed frame with exact article-body quote, selection
hash, factor identity, mechanism family, phase, direction (including UNKNOWN), scope
and reviewer/time provenance. It checks the existing immutable body capture and maps
the declared factor into the atlas. It does not automatically extract/approve events
from arbitrary RSS or use a keyword patch per article. Reviewer attribution still
requires scope/applicability review. A captured article is not current-source approval.

```powershell
python -m engine.impact_events --atlas source-cache/NEW_ATLAS --frame LOCAL_EVENT_JSON --selection LOCAL_SELECTION_JSON --articles LOCAL_ARTICLE_ARCHIVE --output source-cache/NEW_ASSESSMENT.json
```

Bounded directed candidate paths use at most three structural and two mechanism
edges, matching the existing profile layer. They remain separate from the canonical
two-hop alert graph. Atlas highlighting shows graph ancestors for inspection, not
accepted causal paths. An operator may also run hypothetical `impact_atlas scenario`
with a `Scenario` JSON; lag/duration are explicit assumptions, never inferred defaults.

## D. Event-group evaluation — synthetic checks implemented; empirical work pending

The seven families have 42 synthetic combinations of direction and event phase, plus
source/identity/time/quote/revocation-status and exposure-unit regressions. These tests
prove contracts and safety boundaries, not real-world precision or severity accuracy.
`config/impact-group-acceptance.json` predeclares empirical targets and label dimensions.
Cases must be split by independently reviewed economic event clusters, not URLs or
correlated article/narrative pairs. Keep training/calibration/holdout separated and
freeze database, mechanism policy and predictions before independent labeling.

Use prior blind cohorts only for diagnosis. The sourced Sandisk financing example is
a development demonstration using an already-exposed article, not a new holdout win.
Future blind work should identify errors in extraction, exposure data, applicability,
direction, timing and strength separately. Validate one family across multiple companies
and counterexamples before extending coverage; restore missing Micron source coverage.

## E. Weight calibration — deliberately not started before data gates

Policy `uncalibrated-v1` stores `weights:null`. Financial magnitude, realized effect and
path strength remain unknown; a topological route does not establish impact. Independent
support for exposure share, event intensity, transmission, mitigants and timing is needed
before calibration. Future policy versions must be frozen and evaluated on fresh clusters;
do not convert AI relevance agreement into calibrated financial impact probability.

## F. Product delivery — existing private feed retained, live push disabled

The new atlas offers profile selection, structural/mechanism views, source quotes,
narrative ancestor highlighting, coverage gaps, component inspection and offline mobile
layout. It makes no network requests. Private data is embedded in the exported HTML:
keep it under ignored source-cache, do not publish it as a static website. Opening a source
link is a deliberate navigation. No new gateway/API route or cloud deployment is added.
Event bundling, accepted severity/horizon cards and production push remain gated on B–E
and the existing product acceptance requirements. No production-complete claim is made.
