# Source statement role

`source-role-v1` adds a bounded discourse check after a news statement has already
matched its own resource or infrastructure asset. Company applicability still comes
from sourced profiles, graph paths and declared narrative intents. It does not use
ticker branches, rewrite news, infer actors or change numerical priority weights.

| Role | Interpretation | Routing |
| --- | --- | --- |
| `INCIDENTAL_DESCRIPTION` | Explicit persistent state/capability without matching headline focus | Withhold this candidate; continue examining independent statements |
| `FOCUSED_DESCRIPTION` | The description itself has explicit headline focus | Context only; cannot independently become priority |
| `OPERATING_OR_EXPLANATORY_CONTEXT` | No supported descriptive marker found | Continue existing applicability/priority checks; not a verified new event |

Markers cover a bounded set of persistent-state constructions with a supplied
historical period, equipment/capability descriptions, and explicit specialization.
Examples: “has maintained power availability since 2021”, “is equipped with power
capacity”, and “specializes in building data centers”. All periods remain literal
source text; they are not estimates of impact duration.

For infrastructure action/object matching, the capability marker must govern that
action directly. A company description before a separate project announcement does
not erase the project. A later substantive candidate in the same sentence or another
sentence can qualify even when the earlier candidate is only descriptive. The typed
market classifier records capability as BACKGROUND; generic priority cannot rescue it.

A headline can retain a descriptive context only when the required resource/market
or action/asset focus occurs in one headline clause. It cannot provide missing source
evidence, bridge unrelated clauses or establish a company relationship. Body-unit
callers use the existing original `context_title`; RSS uses the original title. A
secondary substantive development need not repeat its topic in the headline.

Trace fields preserve the original clause/description spans and reason. Context-only
cards explain in Vietnamese that the passage describes existing capability or state,
not a new change. Readiness matches retain their previous context-only behavior.
Source hashes, revisions, withdrawals, valid times and exact sourced paths remain
mandatory; profiles/targets/labels are unchanged in this rollout.

This is a narrow English discourse guard, not a complete primary-event or factual
truth classifier. Unrecognized descriptions can still match; metaphorical headlines,
implicit references and complex coordination can be missed. Existing full-article
About/forward-looking appendix suppression is unchanged. Independent unused-event
evaluation and financial-impact validation remain separate work.

See [review](../reports/source-focus-review.md) for per-step benchmark results and
the controlled local feed comparison. Data remains local; delivery and cloud are off.
