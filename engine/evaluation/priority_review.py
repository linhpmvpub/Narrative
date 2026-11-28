"""Two independent AI dimensions: informational relevance and editorial priority.

This local review never authorizes notifications or estimates financial effects.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from engine.atlas_freeze import runtime_fingerprint
from engine.company_profiles import available_bundles
from engine.core_activity import assess
from engine.core_decisions import POLICY
from engine.evaluation.company_quality import LABELS, SCORE_POLICY, company_id
from engine.evaluation.grouped_relevance import connected_clusters, metrics
from engine.evaluation.profile_relevance import consensus, write_new
from engine.ingestion.contracts import digest
from engine.profile_news import entity_context
from engine.profile_routing import binding_decisions
from engine.source_sentences import source_units

GROUPS = {"supply_disruption", "input_price", "capacity", "demand", "technology",
          "financing", "policy", "other", "UNKNOWN"}
RUBRIC = {
    "reference_kind": "AI_INDEPENDENT_REVIEW_NOT_HUMAN_GOLD",
    "relevance": {
        "RELEVANT": "Supplied news has a defensible connection to the stated narrative through the supplied company scope. Conditional relevance is allowed; no price forecast or quantified impact required.",
        "NOT_RELEVANT": "Outside this narrative/product/company scope; company name or generic AI theme alone is insufficient.",
        "INSUFFICIENT_CONTEXT": "Excerpt or supplied profile cannot establish whether the connection applies."},
    "priority": {
        "PRIORITY": "Relevant AND describes a concrete new decision, operational change, constraint, transaction, release or scoped policy development worth highlighting in a research feed. A specific forward-looking plan may qualify, explicitly as a plan. This is editorial judgment, not a push authorization or profit effect.",
        "CONTEXT": "Relevant explanatory/background/theme item without a sufficiently concrete development in this excerpt. Routine conference notices, evergreen promotion and sponsored educational content normally belong here if relevant.",
        "NONE": "Use only for NOT_RELEVANT.",
        "INSUFFICIENT_CONTEXT": "Insufficient evidence to distinguish a priority development from context; required when relevance is unresolved."},
    "event_groups": "Label the actual event described, not mere vocabulary: financial-services adoption is not financing; a funding/borrowing transaction is. Use one to three groups, other or UNKNOWN alone. Keep groups identical for all pairs of the same article.",
    "event_groups_values": sorted(GROUPS),
    "instructions": "Use supplied packet only, no browsing or predictions/peer labels. Do not fill missing facts. Treat claims as source-reported, not independently verified. Explain each pair's relevance and priority briefly in rationale. No human gold or filesystem isolation claim.",
}
COMPANY_RUBRIC = {
    "RELEVANT": "The reported event has a defensible direct or conditional connection to this company's supplied business/product/customer/supplier/market scope, whether or not any watched narrative fits. A name or generic AI theme alone is insufficient. Do not infer a transaction with an unnamed supplier.",
    "NOT_RELEVANT": "Outside the supplied company's business scope, with no defensible connection in this source.",
    "INSUFFICIENT_CONTEXT": "Source excerpt or supplied company dossier does not establish whether this company is affected. Do not fill missing source facts.",
    "instructions": "Label company relevance independently first, then narrative relevance and priority. A RELEVANT narrative requires RELEVANT company. A RELEVANT company may have zero relevant watched narratives. No stock-return prediction, causal verification or quantified effect implied.",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def decisions(row, bundle, narrative, at, policy):
    article = row["article"]
    units = [article]
    if "source_observation" in row:
        from engine.article_cards import substantive_blocks

        blocks, _ = substantive_blocks(row["source_observation"], at)
        units = [{"title": article["title"], "summary": ""}] + [
            {"title": "", **unit, "context_title": article["title"]}
            for block in blocks for unit in source_units(block["text"])]
    assessments, matched = [], False
    for unit in units:
        links = []
        for d in binding_decisions(bundle, narrative, unit, at):
            if d["paths_truncated"] or len(d["path"]) > policy["max_hops"]:
                continue
            ref = d["binding"].entity_reference_id
            links.append({"matches": d["matches"], "entity_context": entity_context(
                bundle, ref, unit, at) if ref else None})
        matched |= bool(links)
        assessments.append(assess({"headline": article.get("title", ""),
                                   "excerpt": unit.get("summary", "")}, links, policy))
    activity = max(assessments, key=lambda a: a["editorial_score"])
    # Keep the winning assessment/rank unchanged, but do not lose withholding
    # evidence from equal-scoring body units behind the first title assessment.
    audit = {key: sum(a["priority_audit"][key] for a in assessments) for key in
             ("matched_links", "context_only_links", "scoped_assertion_links", "eligible_windows", "concrete_signals")}
    return matched, {**activity, "review_audit": {**audit, "source_units": len(units)}}


def freeze(directory, profile_root, review_directory, *, company_scope=False):
    """Add locked baseline/broader decisions and a prediction-free compact packet."""
    directory, review_directory = Path(directory), Path(review_directory)
    if review_directory.exists() or (directory / "priority-freeze.json").exists():
        raise ValueError("New review directory/freeze required")
    packet, original = read(directory / "packet.json"), read(directory / "freeze.json")
    if digest(packet) != original["packet_sha256"]:
        raise ValueError("Original packet changed")
    at = datetime.fromisoformat(original["at"])
    registry = available_bundles(at, root=Path(profile_root))
    if not registry["enabled"] or registry["withheld"] or registry["truncated"]:
        raise ValueError("Complete validated profiles required")
    bundles = {b.id: b for b in registry["items"]}
    policy, runtime = read(POLICY), runtime_fingerprint()
    predictions: dict = {}
    profiles: dict = {}
    articles: dict = {}
    clusters = connected_clusters(packet)
    for row, cluster in zip(packet, clusters, strict=True):
        bundle = bundles[row["profile_id"]]
        if digest(bundle.model_dump(mode="json")) != row["profile_sha256"]:
            raise ValueError("Profile differs from packet")
        narrative = next(n for n in bundle.narratives if n.id == row["narrative"]["id"])
        matched, activity = decisions(row, bundle, narrative, at, policy)
        predictions[row["id"]] = {"matched": matched, "baseline": matched
                                  and activity["tier"] not in {"BACKGROUND_THEME", "SPONSORED_RESEARCH"},
                                  "broader": matched and not activity["sponsored"],
                                  "event_cluster": cluster, "assessment": activity}
        profile = profiles.setdefault(bundle.id, {k: row.get(k, []) for k in
                    ("profile_id", "ticker", "nodes", "relationships", "sources", "entity_references", "components")})
        profile.setdefault("narratives", {})[narrative.id] = row["narrative"]
        article = articles.setdefault(row["cluster"], {"cluster": row["cluster"],
                                      "article": row["article"], "pairs": []})
        article["pairs"].append({"id": row["id"], "profile_id": bundle.id,
                                 "narrative_id": narrative.id})
    compact = {"packet_sha256": digest(packet), "profiles": list(profiles.values()),
               "articles": list(articles.values()), "rubric": RUBRIC}
    if company_scope:
        compact["rubric"] = {**RUBRIC, "company_relevance": COMPANY_RUBRIC}
        units: dict = {}
        for row in packet:
            key = company_id(row, row["ticker"])
            unit = units.setdefault(key, {"id": key, "cluster": row["cluster"],
                                          "ticker": row["ticker"], "profile_id": row["profile_id"],
                                          "pair_ids": []})
            unit["pair_ids"].append(row["id"])
        compact["company_units"] = list(units.values())
    if runtime != runtime_fingerprint():
        raise ValueError("Runtime changed during freeze")
    after = available_bundles(at, root=Path(profile_root))
    if [digest(b.model_dump(mode="json")) for b in after["items"]] != [
            digest(b.model_dump(mode="json")) for b in registry["items"]]:
        raise ValueError("Profile registry changed during freeze")
    receipt = {"at": datetime.now(UTC).isoformat(), "original_freeze_sha256": digest(original),
               "packet_sha256": digest(packet), "predictions_sha256": digest(predictions),
               "compact_sha256": digest(compact), "rubric_sha256": digest(compact["rubric"]),
               "runtime": runtime, "policy_sha256": digest(policy),
               "clusters": len(set(clusters)), "pairs": len(packet), "delivery": "disabled",
               "candidate": "ALL_SOURCE_MATCHED_NON_SPONSORED_CONTEXT_LOCKED_BEFORE_LABELS",
               "promotion": "NO_AUTOMATIC_PROMOTION; require existing group/product gates and priority evidence"}
    if company_scope:
        receipt.update(company_units=compact["company_units"], score_policy=SCORE_POLICY)
    write_new(directory / "priority-predictions.json", predictions)
    write_new(directory / "priority-freeze.json", receipt)
    review_directory.mkdir(parents=True)
    write_new(review_directory / "packet.json", compact)
    write_new(review_directory / "receipt.json", {k: receipt[k] for k in
              ("at", "packet_sha256", "compact_sha256", "rubric_sha256", "clusters", "pairs")})
    return receipt


def company_consensus(reviews, units):
    """Validate direct company votes independently of narrative agreement."""
    ids, maps = {u["id"] for u in units}, []
    if len(reviews) != 2:
        raise ValueError("Two company reviewers required")
    for review in reviews:
        votes = review.get("company_labels", [])
        if len(votes) != len(ids) or {v["id"] for v in votes} != ids:
            raise ValueError("Company review coverage incomplete or duplicated")
        if any(v["relevance"] not in LABELS or not v.get("rationale", "").strip() for v in votes):
            raise ValueError("Invalid company review label")
        by_id = {v["id"]: v for v in votes}
        pairs = {v["id"]: v for v in review["labels"]}
        for unit in units:
            if (any(pairs[k]["relevance"] == "RELEVANT" for k in unit["pair_ids"])
                    and by_id[unit["id"]]["relevance"] != "RELEVANT"):
                raise ValueError("Company/narrative reference contradiction")
        maps.append(by_id)
    labels, disagreements = [], 0
    for unit in units:
        a, b = (m[unit["id"]] for m in maps)
        agree = a["relevance"] == b["relevance"]
        disagreements += not agree
        labels.append({**unit, "relevance": a["relevance"] if agree else "INSUFFICIENT_CONTEXT",
                       "rationale": "Reviewer A: " + a["rationale"] + " Reviewer B: " + b["rationale"]})
    return {"labels": labels, "disagreements": disagreements}


def validate_review(review, packet, frozen):
    if datetime.fromisoformat(review["reviewed_at"]) < datetime.fromisoformat(frozen["at"]):
        raise ValueError("Review must follow priority prediction freeze")
    if review.get("rubric_sha256") != frozen["rubric_sha256"]:
        raise ValueError("Wrong priority rubric")
    rows = {r["id"]: r for r in packet}
    groups_by_article: dict = {}
    for vote in review["labels"]:
        label, priority = vote["relevance"], vote["priority"]
        allowed = {"RELEVANT": {"PRIORITY", "CONTEXT", "INSUFFICIENT_CONTEXT"},
                   "NOT_RELEVANT": {"NONE"}, "INSUFFICIENT_CONTEXT": {"INSUFFICIENT_CONTEXT"}}
        if label not in allowed or priority not in allowed[label]:
            raise ValueError("Inconsistent relevance/priority")
        groups = vote["event_groups"]
        if (not isinstance(groups, list) or not 1 <= len(groups) <= 3
                or len(set(groups)) != len(groups) or not set(groups) <= GROUPS
                or len(groups) > 1 and bool({"UNKNOWN", "other"} & set(groups))):
            raise ValueError("Invalid event groups")
        cluster = rows[vote["id"]]["cluster"]
        if cluster in groups_by_article and groups_by_article[cluster] != set(groups):
            raise ValueError("Article group labels differ across narratives")
        groups_by_article[cluster] = set(groups)


def evaluate(directory, review_paths):
    directory = Path(directory)
    packet, base = read(directory / "packet.json"), read(directory / "freeze.json")
    frozen, predictions = read(directory / "priority-freeze.json"), read(directory / "priority-predictions.json")
    if (digest(base) != frozen["original_freeze_sha256"] or digest(packet) != frozen["packet_sha256"]
            or digest(predictions) != frozen["predictions_sha256"]
            or set(predictions) != {r["id"] for r in packet}):
        raise ValueError("Frozen prediction or packet changed")
    if base.get("prediction_track") == "full_article_relevance":
        from engine.evaluation.article_relevance import verify_frozen

        verify_frozen(directory, packet, base)
    combined = consensus(directory, review_paths)  # Strict identity, declarations, coverage and timestamps.
    reviews = [read(p) for p in review_paths]
    for review in reviews:
        validate_review(review, packet, frozen)
    if "company_units" in frozen:
        expected: dict = {}
        for row in packet:
            key = company_id(row, row["ticker"])
            unit = expected.setdefault(key, {"id": key, "cluster": row["cluster"],
                                            "ticker": row["ticker"], "profile_id": row["profile_id"],
                                            "pair_ids": []})
            unit["pair_ids"].append(row["id"])
        if frozen["company_units"] != list(expected.values()) or frozen["score_policy"] != SCORE_POLICY:
            raise ValueError("Frozen company units or score policy changed")
        combined["company"] = company_consensus(reviews, frozen["company_units"])
    maps = [{v["id"]: v for v in r["labels"]} for r in reviews]
    by_id = {r["id"]: r for r in packet}
    rows, priority_disagreements, group_disagreements = [], 0, set()
    for vote in combined["labels"]:
        row = by_id[vote["id"]]
        a, b = (m[vote["id"]] for m in maps)
        priority_disagreements += a["priority"] != b["priority"]
        priority = a["priority"] if a["priority"] == b["priority"] else "INSUFFICIENT_CONTEXT"
        if vote["relevance"] == "INSUFFICIENT_CONTEXT":
            priority = "INSUFFICIENT_CONTEXT"
        groups = a["event_groups"] if set(a["event_groups"]) == set(b["event_groups"]) else ["UNKNOWN"]
        if groups == ["UNKNOWN"]:
            group_disagreements.add(row["cluster"])
        rows.append({"id": row["id"], "ticker": row["ticker"], "groups": groups,
                     "label": vote["relevance"], "priority_label": priority, **predictions[row["id"]]})
        vote.update(priority=priority, event_groups=groups)
    result = {"schema": "DUAL_RELEVANCE_PRIORITY_REVIEW_V1", "delivery": "disabled",
              "reference_kind": "TWO_INDEPENDENT_AI_REVIEWS_NOT_HUMAN_GOLD",
              "pairs": len(rows), "clusters": frozen["clusters"],
              "priority_disagreements": priority_disagreements,
              "relevance_disagreements": combined["disagreements"],
              "group_unresolved_clusters": len(group_disagreements),
              "freeze_sha256": digest(frozen), "rubric_sha256": frozen["rubric_sha256"],
              "review_sha256": combined["review_sha256"], "promotion": "NOT_PROMOTED",
              "possible_duplicate_clusters": [flag for review in reviews
                                               for flag in review.get("possible_duplicate_clusters", [])],
              "cluster_independence": "LEXICAL_CLUSTERING_WITH_REVIEW_FLAGS_NOT_VERIFIED_ECONOMIC_IDENTITY",
              "variants": {}}
    for variant in ("matched", "baseline", "broader"):
        priority_rows = [{**r, "label": "RELEVANT" if r["priority_label"] == "PRIORITY"
                          else "INSUFFICIENT_CONTEXT" if r["priority_label"] == "INSUFFICIENT_CONTEXT"
                          else "NOT_RELEVANT"} for r in rows]
        result["variants"][variant] = {
            "relevance": metrics(rows, lambda r, v=variant: r[v]),
            "priority": metrics(priority_rows, lambda r, v=variant: r[v]),
            "by_ticker": {t: metrics([r for r in rows if r["ticker"] == t],
                                    lambda r, v=variant: r[v]) for t in ("AMD", "MU", "SNDK", "NVDA", "DELL")},
            "by_group": {g: metrics([r for r in rows if g in r["groups"]],
                                   lambda r, v=variant: r[v]) for g in sorted(GROUPS)}}
    write_new(directory / "dual-consensus.json", combined)
    write_new(directory / "dual-evaluation.json", result)
    return result
