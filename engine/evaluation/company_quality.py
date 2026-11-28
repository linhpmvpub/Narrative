"""Separate company discovery from narrative attribution; no routing changes.

The headline is a fixed-cohort development index, never market accuracy or a
release gate. Unknown labels reduce its evidence coverage rather than become TNs.
"""

from collections import defaultdict

from engine.evaluation.grouped_relevance import metrics
from engine.ingestion.contracts import digest

SCORE_POLICY: dict = {
    "version": "COMPANY_NARRATIVE_EFFECTIVENESS_V1",
    "weights": {"company": 0.4, "narrative": 0.4, "priority": 0.2},
    "formula": "100 * sum(weight * F1 * resolved_fraction)",
    "requires": "Direct company labels and positive reference support in every dimension",
    "meaning": "Fixed-cohort AI development index; not accuracy, probability or product completion",
}
LABELS = {"RELEVANT", "NOT_RELEVANT", "INSUFFICIENT_CONTEXT"}


def identity(value):
    """Exact source representation, not an economic cluster or a bare URL.

    Keep revisions/full-text observations separate; do not OR unrelated stories
    together merely because a cluster links the same economic event.
    """
    article = value["article"]
    source = {k: article.get(k) for k in ("url", "title", "summary", "published_at")}
    source.update({k: value[k] for k in ("source_observation", "archive_source") if k in value})
    return {"source_unit_id": digest(source),
            "target_id": value["profile_id"] + ":" + value["narrative"]["id"]}


def company_id(value, ticker):
    return digest((identity(value)["source_unit_id"], ticker))


def company_rows(rows):
    """OR delivery across watched narratives, retaining independent company truth.

    Legacy narrative references only support an explicitly scoped proxy. An all
    negative proxy needs every target observed for that ticker in this cohort.
    """
    expected: dict = defaultdict(set)
    grouped: dict = defaultdict(list)
    for row in rows:
        expected[row["ticker"]].add(row["target_id"])
        grouped[(row["source_unit_id"], row["ticker"])].append(row)
    result = []
    for (source, ticker), items in grouped.items():
        targets = {r["target_id"] for r in items}
        if len(targets) != len(items):
            raise ValueError("Duplicate article/company/narrative unit")
        direct = [r["company_label"] for r in items if "company_label" in r]
        if direct:
            if len(direct) != len(items) or len(set(direct)) != 1 or direct[0] not in LABELS:
                raise ValueError("Inconsistent or incomplete direct company references")
            label, kind = direct[0], "DIRECT_COMPANY_REFERENCE"
        else:
            labels = {r["label"] for r in items}
            label = ("RELEVANT" if "RELEVANT" in labels else "NOT_RELEVANT"
                     if targets == expected[ticker] and labels == {"NOT_RELEVANT"}
                     else "INSUFFICIENT_CONTEXT")
            kind = "WATCHED_NARRATIVE_UNION_PROXY_NOT_ALL_COMPANY_NEWS"
        if direct and label == "NOT_RELEVANT" and any(r["label"] == "RELEVANT" for r in items):
            raise ValueError("Narrative relevance contradicts negative company reference")
        discovery = [r["company_selected"] for r in items if "company_selected" in r]
        if direct and discovery and (len(discovery) != len(items) or len(set(discovery)) != 1
                          or any(type(v) is not bool for v in discovery)):
            raise ValueError("Inconsistent company discovery predictions")
        result.append({"id": digest((source, ticker)), "ticker": ticker, "label": label,
                       "source_unit_id": source, "event_cluster": items[0]["event_cluster"],
                       "groups": sorted({g for r in items for g in r["groups"]}),
                       "selected": any(r["selected"] for r in items) or bool(direct and discovery and discovery[0]),
                       "reference_scope": kind,
                       "complete_watched_targets": targets == expected[ticker],
                       "narrative_pairs": len(items)})
    return result


def company_report(rows):
    units = company_rows(rows)
    def score(items):
        return metrics(items, lambda r: r["selected"])
    return {"status": "EXPOSED_REGRESSION", "overall": score(units),
            "reference_scopes": sorted({r["reference_scope"] for r in units}),
            "unit": "Exact source representation x company; direct discovery plus watched narrative selections. Legacy proxies use narrative selections only.",
            "by_company": {t: score([r for r in units if r["ticker"] == t])
                           for t in sorted({r["ticker"] for r in units})},
            "by_group": {g: score([r for r in units if g in r["groups"]])
                         for g in sorted({g for r in units for g in r["groups"]})},
            "incomplete_watched_units": sum(not r["complete_watched_targets"] for r in units)}


def headline(cohorts, config):
    if config is None:
        return {"status": "NOT_CONFIGURED", "score": None}
    if config.get("policy") != SCORE_POLICY or config.get("anchor") not in cohorts:
        raise ValueError("Unknown score policy or anchor; explicitly version the suite")
    anchor = cohorts[config["anchor"]]
    direct = anchor["company"]["reference_scopes"] == ["DIRECT_COMPANY_REFERENCE"]
    components: dict = {}
    missing = []
    for name, key in (("company", "company"), ("narrative", "relevance"), ("priority", "priority")):
        m = anchor[key].get("overall")
        if not m or not m["pairs"] or m["tp"] + m["fn"] == 0:
            missing.append(name)
            components[name] = {"status": "NO_POSITIVE_REFERENCE_SUPPORT"}
            continue
        f1 = 2 * m["tp"] / (2 * m["tp"] + m["fp"] + m["fn"])
        total = anchor[key].get("reference_total_pairs", m["pairs"])
        resolved = (m["pairs"] - m["unresolved"]) / total
        contribution = 100 * SCORE_POLICY["weights"][name] * f1 * resolved
        components[name] = {**m, "f1": f1, "resolved_fraction": resolved,
                            "unlabelled_pairs": total - m["pairs"],
                            "weight": SCORE_POLICY["weights"][name], "points": contribution}
    if not direct:
        missing.append("direct_company_reference")
    return {"status": "AVAILABLE_DEVELOPMENT_INDEX" if not missing else "INSUFFICIENT_REFERENCE_SUPPORT",
            "score": round(sum(c["points"] for c in components.values()), 2) if not missing else None,
            "scale": [0, 100], "anchor": config["anchor"], "policy": SCORE_POLICY,
            "components": components, "missing_support": missing,
            "comparison_rule": "Same suite hash, anchor and policy only; no cross-sample gain claims"}
