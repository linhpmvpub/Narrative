# Company discovery before narrative attribution

The investor should be able to find relevant company context even when no watched
narrative covers it. The shared pipeline is captured RSS revision → reviewed
company scope → independently qualified narrative → explanation. Discovery never
creates a canonical event, verifies a customer or infers a financial effect.

## Data contract

`ProfileBundle.company_discovery` contains optional versioned, expiring rules.
Existing profiles remain byte-equivalent when the field is empty.

- `ISSUER_EVENT`: explicitly reviewed aliases quoted in primary profile evidence.
  Shared bounded English syntax recognizes results, financing, governance and
  credit-rating developments. A name mention alone is insufficient. The source
  remains unverified; alias curation still needs review, not just a substring check.
- `FACTOR_EXPOSURE`: an existing reviewed binding, exact one/two-edge factor path,
  and a separate company membership path to the same product/segment/metric.
  Membership is limited to SELLS/HAS_SEGMENT/HAS_METRIC, at most three edges.
  A customer/competitor connection is not ownership. Active source-backed edges,
  review time, effective time, exact required mechanism and typed business intents
  are checked at read time. Scope is profile data, never a ticker branch.
- `company_only` bindings support structured activity/economic change with no
  narrative target. They require a corresponding discovery rule and are excluded
  from narrative routing. Missing narratives do not justify fabricating one.

The two paths explain exposure and company membership separately. They do not
assert a causal flow in reverse, a supplier contract, demand volume or impact size.
Common financing/access/market guards still apply; declaring a company scope
cannot override an existing narrative's intent.

## Private feed and interface

`candidate_feed(..., include_company=True)` reuses current source/revision,
withdrawal, raw RSS capture, conflict, publication-time and age checks. The core
feed additionally checks the pinned profile digest and successful-source freshness.
An article-company has one card: existing narrative cards carry discovery evidence;
otherwise it appears in `company_context` with no narrative assignment. Both paths
are bounded and disclose truncation. Corrections change the revision digest;
withdrawn, stale, conflicting, uncaptured or unpinned inputs are withheld.

`/core` displays the separate company section, exact source spans, source links and
directed relationship diagrams. Filter and logout apply to this section as well.
The existing authenticated API remains in use. Discovery has no editorial-priority
promotion: direction, financial magnitude and horizon remain UNKNOWN; delivery is
disabled. A local snapshot browser test does not establish remote-service uptime.

## Measurement and limitations

See [benchmark contract](quality-benchmark.md). Direct company references measure
discovery OR narrative selection; legacy narrative-union proxies exclude broader
discovery. Neither formula, frozen labels nor narrative targets change. Report
company gains separately; finding a company cannot repair a wrong narrative.

The initial five-company implementation is deliberately bounded. Narrow English
issuer syntax, incomplete product/market evidence, incidental infrastructure prose
and sparse reference support remain limitations. Reviewed full-body matching has a
shared entry point, but production company-context delivery currently uses RSS
title/excerpt. Next enrich source-local substantive evidence, then evaluate unused
event families with independent AI labels before tuning ranking. Human usefulness,
personalization, financial effects and operational release gates remain separate.
