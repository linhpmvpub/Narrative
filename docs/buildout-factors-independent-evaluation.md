# Financing, permitting and compute access

NVDA local supply profile v3 adds three source-backed factors and four reviewed literal bindings: customer infrastructure finance, data-center permitting/restrictions, AI training/inference compute access, and a separately scoped AI/energy permitting-policy signal. Existing SEC paragraphs explicitly discuss capital, investment-grade financing capacity, regulatory/construction challenges, permitting delays and compute demand. Original capture/publication times remain unchanged; new profile/narrative availability is the actual review time. Three directed conditional paths reach the customer-buildout narrative; the company structural links establish exposure. No global graph approval, canonical event or notification is created.

These signals do not equate a policy proposal with enacted law, sector demand with an NVIDIA order, a customer's funding with NVIDIA debt, or compute access with realized revenue. Scope, project/customer identity, effective date and financial magnitude remain unknown unless separately sourced. The literal rules still need contextual review and can miss paraphrases.

The local development feed now shows five cards rather than one. This is an exposed development-set result, not held-out improvement. Mobile390/desktop1440 source links, details, refresh failure/recovery, logout clearing and overflow checks passed. Raw profile version and source evidence remain under ignored source-cache.

## Fresh evaluation protocol

`engine.evaluation.profile_relevance freeze` accepts repeated `--exclude-packet` paths. Prior packet hashes must match their freeze receipts. Exclusion uses normalized URL identity (including later corrections at the same URL), then word-trigram Jaccard >=0.8 across title/excerpt; the same near-duplicate rule also groups selected articles. This is declared text-overlap control, not proof of semantic event independence or absence of model pretraining exposure.

For this batch, the two earlier evaluation packets were excluded. The inbox contained only12remaining eligible URLs/48article-narrative pairs, not100fresh cases. The original requested count and actual count are recorded. Frozen directory: source-cache/profile-independent-2026-11-22. Reviewer-only copy: source-cache/profile-independent-review-packet with packet.json, receipt.json and RUBRIC.txt; no predictions or prior labels. Separate folders are a process boundary, not filesystem ACL isolation. Predictions remain in the frozen evaluation directory and must not be given to reviewers.

Two independently assigned AI reviewers can produce AI_INDEPENDENT_REVIEW files with distinct reviewer_id, truthful predictions_accessed=false/peer_labels_accessed=false, actual reviewed_at after freeze, exact packet_sha256 and one rationale/label per pair. Labels are RELEVANT, NOT_RELEVANT or INSUFFICIENT_CONTEXT. Run:

```powershell
python -m engine.evaluation.profile_relevance consensus --directory source-cache/profile-independent-2026-11-22 --review source-cache/reviewer-a.json --review source-cache/reviewer-b.json
python -m engine.evaluation.profile_relevance evaluate --directory source-cache/profile-independent-2026-11-22 --labels source-cache/profile-independent-2026-11-22/consensus.json
```

Consensus output uses exclusive creation. Same-reviewer submissions, incomplete/duplicate labels, wrong packet hashes, future/pre-freeze review times, missing rationale and declared prediction/peer access are rejected. Disagreements remain INSUFFICIENT_CONTEXT; they are not silently adjudicated by the implementation agent. Two-agent agreement is an AI reference, not human gold or independent causal truth. Retain disagreements for a separately authorized adjudication pass. A human-review route should preserve explicit human provenance rather than use the AI consensus format.

At preparation time, reviewer method (two separate-context AI agents or human reviewers) was requested and remains pending. No independent labels or accuracy have been fabricated. The packet and predictions remain ready for the next step. This small convenience sample may lack positive cases; report undefined precision/recall when denominators are zero. Any future rule tuning must use a development partition and be evaluated against another untouched sample.
