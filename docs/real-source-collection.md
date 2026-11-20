# SEC collection handoff

`python -m engine.collect_sec` stages real filing documents for review. It does not approve identities/rights in the production database, infer economic events, assign materiality, label gold cases or activate graph edges. No bulk collection was run without a genuine contact User-Agent.

Supply a real project/contact User-Agent as described by the [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions). The existing SourceClient serializes requests at <=2/second, limits decoded bodies to 5 MB, bounds retries and refuses redirects. The [SEC developer guidance](https://www.sec.gov/about/developer-resources) documents fair access. No contact identity is fabricated.

```powershell
python -m engine.collect_sec --user-agent 'YourProject actual-contact@your-domain' --start 2025-02-21 --end 2026-11-20 --per-company 10 --output source-cache/sec-review-2026-11-20
```

The date range is explicit; adjust it intentionally. This selects up to 10 recent 10-K/10-Q/8-K filings or amendments per company from the current submissions feed, not a guarantee of 50 independent events. Older paginated submissions are not silently fetched or inferred. Recent indexes may contain fewer qualifying filings; unavailable/oversized documents are recorded as acquisition errors, not success.

The collector checks the official ticker index against each submissions CIK/ticker; all five issuers must be distinct. SNDK candidates before separation are excluded, and WDC submissions cannot substitute for SNDK. HTML basenames and accession numbers are validated before constructing SEC archive URLs. The review folder contains source files, SHA256 hashes, actual retrieval timestamps and a progressively saved `collection.json`. The directory must be new to preserve earlier evidence.

Every staged record remains `rights_status:pending_review`, `label_status:unlabeled`, `canonical_event_key:null`, `historical_as_of_eligible:false`. Today's downloads cannot be backdated into a historical replay. An independent reviewer must establish source rights, verify issuer/period lineage, extract source-backed claims, deduplicate economic events, approve graph/materiality inputs, and complete gold labels. Historical evaluation needs genuinely captured historical snapshots or a separately reviewed archive reconstruction approach; otherwise begin a prospective shadow collection from actual capture times.

Required next inputs: real SEC contact email; independent reviewer/source approval; Threadnote host repository/auth contracts; deployment domain/provider and production secret-management choices. No user, tenant, author, reviewer or license approval will be invented to close these gates.
