# Shared news classification and narrative routing

Version: news-routing-v1; core editorial policy7, numerical weights unchanged.
This is an opt-in local candidate, not release acceptance or push authorization.

## End-to-end responsibilities

| Stage | Existing owner | Contract and current boundary |
|---|---|---|
| Crawl and normalize | adapters/news, news, news_capture | Public RSS/allowed public article capture, publication and observation times; raw bodies stay local. X still requires credentials. |
| Deduplicate and track versions | news ingestion and article capture | Source identity, revisions, withdrawal and immutable capture checks precede eligibility; lexical groups are not verified economic-event identity. |
| Classify source assertions | news_framework, news-routing-v1.json | Shared component, market and readiness activity vocabulary; original spans and source-only classification. No company branch, actor attribution or invented financial fact. |
| Bind to database | company_profiles, profile_news | CLASSIFIED_CONTEXT explicitly references sourced company input factors and narratives. Missing component evidence or routing policy fails validation. |
| Traverse and scope | profile_routing, news_framework | Existing verified/time-valid graph paths; COMPETES_WITH requires COMPETITION intent, readiness requires SUPPLY or DEPLOYMENT. A rejected short path cannot mask another eligible path. |
| Rank and explain | core_activity, core_decisions, web/core.js | Existing editorial ranking; retain context role and concise conditional explanation. Source context is separate from verified orders/demand/financial magnitude. |
| Evaluate | evaluation/article_relevance, priority_review | Freeze predictions before two independent AI reviews, relevance and priority separately, unresolved retained. Exposed cohorts remain regression. |
| Deliver | existing notification gates | Disabled. No cloud, server or tunnel changes. Product/user acceptance and later explicit authorization still required. |

RSS and complete-body matching use the same routing contract. Legacy profiles without
new optional fields preserve serialized hashes and behavior. New profiles declare
SUPPLY, DEPLOYMENT, DEMAND and/or COMPETITION per narrative; the declaration is curated
profile data, not a prediction learned from headlines. Competition context has a
separate local MU narrative; previous narrative targets and evaluation labels are retained.

## Shared signal contract

A positive input-readiness signal requires a component, DATA_CENTER market and
readiness activity in one sentence/window of at most1200characters. A title cannot
donate market scope to another sentence. Negation/uncertainty markers withhold this
classifier. The ontology has MEMORY, COOLING, PACKAGING and NETWORKING classes;
this candidate only activates sourced memory bindings in AMD/NVDA/DELL. Classification
coverage is not sourced exposure coverage. Schema validation checks literal source
support, not semantic truth of the whole source statement.

Each selected path retains source/version checks, signal spans, relation types,
narrative intents, role, explanation and UNKNOWN financial impact. Input readiness
does not establish that the issuer supplies this particular company. Competition
does not establish own production, market-share loss or earnings direction.

## Extension and limitations

Add a company through sourced factors/relationships and explicit narrative intents.
Extend vocabulary by event class with renamed-company, positive/negative market,
negation, withdrawal and expired-edge tests. Do not add ticker/headline exceptions
or tune on a newly inspected holdout. Old literal binding kinds still coexist with
the shared classifier; this is not a complete semantic parser or a migration of
all event classes. It may miss paraphrases, cross-sentence evidence or unmodeled
competitors; same-window co-occurrence can still misattribute an assertion.

Separately measure article→company coverage and article→narrative precision/recall.
Moving a result to a new competition narrative does not erase a miss on an original
supply target. New independent labels inform a later development cycle, not silent
replacement of the older reference. Financial magnitude/horizon remain unknown
without scoped evidence. Local cohort sources, labels and detailed profiles are
excluded from GitHub; publish only aggregate results.

Local workspace: source-cache/framework-routing-workspace-2026-11-27.json.
Candidate profiles, atlas, registry, freeze and independent-review evidence:
source-cache/framework-routing-2026-11-27. See the latest CHECKPOINT and QUALITY_REVIEW
for final test, holdout and CI results.
