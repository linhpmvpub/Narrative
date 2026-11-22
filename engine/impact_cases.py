"""Private event-scoped impact cases; reported accounting effects, not price forecasts."""

import hashlib
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from engine.accounting_evidence import comparable_periods, corroborate_companyfacts, extract
from engine.ingestion.contracts import digest
from engine.news_articles import normalized_text
from engine.settings import Settings


def verified_file(root, relative, sha):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path.stat().st_size > 5_000_000:
        raise ValueError("Invalid case artifact path/size")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != sha:
        raise ValueError("Case artifact integrity mismatch")
    return body.decode("utf-8")


def build(spec, documents):
    # First validated issuer-specific case; do not generalize identity by ticker text.
    if spec["ticker"] != "NVDA" or str(spec["cik"]).zfill(10) != "0001045810":
        raise ValueError("Unsupported or mismatched case issuer")
    expected_concepts = {
        "revenue": "us-gaap:Revenues",
        "gross_profit": "us-gaap:GrossProfit",
        "cost_of_revenue": "us-gaap:CostOfRevenue",
        "charge": "us-gaap:CostOfRevenue",
    }
    if any(spec["operands"].get(k, {}).get("concept") != v for k, v in expected_concepts.items()):
        raise ValueError("Unsupported accounting concepts")
    expected = f"https://www.sec.gov/Archives/edgar/data/{int(spec['cik'])}/{spec['accession'].replace('-', '')}/"
    if (
        not spec["sources"]["filing"]["url"].startswith(expected)
        or spec["sources"]["facts"]["url"]
        != f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(spec['cik']):010d}.json"
    ):
        raise ValueError("Filing identity URL mismatch")
    filing = documents["filing"]
    text = normalized_text(filing.encode())
    quote = spec["mechanism_quote"]
    if not quote or len(quote) > 2000 or quote not in text:
        raise ValueError("Mechanism quote not in filing")
    base = {"cik": spec["cik"], "start": spec["start"], "end": spec["end"]}
    operands = {
        name: extract(filing, **base, **request) for name, request in spec["operands"].items()
    }
    required = {"revenue", "gross_profit", "cost_of_revenue", "charge"}
    if not required <= operands.keys():
        raise ValueError("Missing accounting operands")
    if any(operands[k]["dimensions"] for k in ["revenue", "gross_profit", "cost_of_revenue"]):
        raise ValueError("Consolidated accounting operands required")
    if not operands["charge"]["dimensions"]:
        raise ValueError("Charge needs explicit expense scope")
    if operands["charge"]["concept"] != operands["cost_of_revenue"]["concept"]:
        raise ValueError("Charge must be a component of the same cost concept")
    r, g, c, q = (
        Decimal(operands[k]["value"])
        for k in ["revenue", "gross_profit", "cost_of_revenue", "charge"]
    )
    if not r > 0 or not 0 <= q <= c or r - c != g:
        raise ValueError("Accounting identity or bounded charge check failed")
    facts = json.loads(documents["facts"])
    corroboration = {
        k: corroborate_companyfacts(facts, operands[k], spec["accession"], spec["cik"])
        for k in ["revenue", "gross_profit", "cost_of_revenue"]
    }

    def pct(n, d):
        return str((n / d * 100).quantize(Decimal("0.01")))

    sources = [
        {"role": k, "url": v["url"], "sha256": v["sha256"], "retrieved_at": v["retrieved_at"]}
        for k, v in spec["sources"].items()
    ]
    result = {
        "id": spec["id"],
        "ticker": spec["ticker"],
        "title": spec["title"],
        "case_scope": "REPORTED_ACCOUNTING_CASE_ONLY",
        "event_period": {"start": spec["start"], "end": spec["end"]},
        "accession": spec["accession"],
        "mechanism_quote": quote,
        "mechanism_span": {"start": text.index(quote), "end": text.index(quote) + len(quote)},
        "sources": sources,
        "operands": operands,
        "crosschecks": corroboration,
        "reported_gross_margin_percent": pct(g, r),
        "recognized_charge_usd": str(q),
        "charge_over_revenue_percent": pct(q, r),
        "charge_over_reported_gross_profit_percent": pct(q, g) if g > 0 else None,
        "conditional_margin_drag_pp": pct(q, r),
        "calculation_basis": "Same filing, USD, GAAP, identical duration; charge/revenue is magnitude, not affected revenue share.",
        "conditional_assumptions": [
            "Hold revenue and all other costs fixed",
            "No demand, pricing, volume, tax or cash-flow counterfactual",
        ],
        "causal_status": "ISSUER_REPORTED_NOT_INDEPENDENT_CAUSAL_IDENTIFICATION",
        "scope_limitations": spec["limitations"],
        "chain": [
            {
                "from": "Issuer-reported triggering event (see source quote)",
                "to": "Product-specific inventory/purchase charge",
                "status": "ISSUER_ATTRIBUTION",
            },
            {
                "from": "Recognized cost-of-revenue charge",
                "to": "Gross profit / gross margin",
                "status": "ACCOUNTING_IDENTITY_CONDITIONAL_ON_FIXED_OTHER_TERMS",
            },
        ],
        "general_graph_eligible": False,
        "stock_price_impact": "UNKNOWN",
        "cash_flow_impact": "UNKNOWN",
        "net_income_effect": "UNKNOWN",
        "materiality": "MEASURED_ACCOUNTING_MAGNITUDE_NOT_CALIBRATED_SCORE",
        "decision_trace": [
            {"gate": "issuer_period_unit_scope", "result": "EXACT_XBRL_CONTEXT"},
            {"gate": "consolidated_crosscheck", "result": "SAME_ACCESSION_SEC_COMPANYFACTS"},
            {"gate": "mechanism", "result": "ISSUER_ATTRIBUTION_NOT_INDEPENDENT_CAUSAL_PROOF"},
            {
                "gate": "effect_size",
                "result": "CHARGE_OVER_REVENUE_CONDITIONAL_ACCOUNTING_MAGNITUDE",
            },
            {"gate": "general_graph_or_price", "result": "WITHHELD"},
            {"gate": "delivery", "result": "DISABLED"},
        ],
        "delivery": "disabled",
    }
    if spec.get("prior_period"):
        period_check = comparable_periods(base, spec["prior_period"])
        prior = {
            k: extract(
                filing, cik=spec["cik"], **spec["prior_period"], concept=operands[k]["concept"]
            )
            for k in ["revenue", "gross_profit", "cost_of_revenue"]
        }
        for value in prior.values():
            corroborate_companyfacts(facts, value, spec["accession"], spec["cik"])
        pr, pg, pc = (
            Decimal(prior[k]["value"]) for k in ["revenue", "gross_profit", "cost_of_revenue"]
        )
        if pr <= 0 or pr - pc != pg:
            raise ValueError("Prior accounting identity invalid")
        result["comparison"] = {
            **period_check,
            "prior": prior,
            "revenue_yoy_percent": pct(r - pr, pr),
            "gross_margin_change_pp": str(((g / r - pg / pr) * 100).quantize(Decimal("0.01"))),
            "causal_allocation": "UNKNOWN_NOT_ALL_CHANGE_IS_H20",
        }
    if "segment_revenue" in operands:
        n = Decimal(operands["segment_revenue"]["value"])
        if not operands["segment_revenue"]["dimensions"] or not 0 <= n <= r:
            raise ValueError("Invalid segment exposure")
        result["baseline_share"] = {
            "percent": pct(n, r),
            "kind": "REPORTED_REVENUE_CATEGORY_SHARE",
            "affected_fraction": "UNKNOWN",
            "not_charge_allocation": True,
        }
    return result


def case_feed(as_of=None):
    if not Settings.from_env().dev_informational_feed:
        return {"items": [], "enabled": False, "delivery": "disabled"}
    at = as_of or datetime.now(UTC)
    if at.tzinfo is None:
        raise ValueError("Aware cutoff required")
    root = Path(os.getenv("IMPACT_CASE_ROOT", "source-cache/impact-cases"))
    output = []
    withheld = 0
    for directory in sorted(root.glob("*"))[:20]:
        if not directory.is_dir():
            continue
        try:
            receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
            if receipt.get("status") != "active":
                raise ValueError("Case withdrawn")
            available = datetime.fromisoformat(receipt["available_at"])
            if available.tzinfo is None or available > at or available > datetime.now(UTC):
                continue
            spec = json.loads(verified_file(directory, "case.json", receipt["case_sha256"]))
            if not receipt["reviews"] or len(receipt["reviews"]) != 3:
                raise ValueError("Three declared reviews required")
            roles = set()
            for entry in receipt["reviews"]:
                review = json.loads(verified_file(directory, entry["file"], entry["sha256"]))
                roles.add(review["role"])
                if (
                    review["input_sha256"] != digest(spec)
                    or review["verdict"] != "ACCEPT_REPORTED_ACCOUNTING_CASE"
                    or review.get("reviewer_kind") != "AI_SIMULATED"
                ):
                    raise ValueError("Review does not cover current inputs")
            if roles != {"retail", "fund", "expert"}:
                raise ValueError("Distinct review roles required")
            documents = {}
            for name, source in spec["sources"].items():
                captured = datetime.fromisoformat(source["retrieved_at"])
                if captured.tzinfo is None or captured > available:
                    raise ValueError("Invalid capture chronology")
                documents[name] = verified_file(directory, source["file"], source["sha256"])
            item = build(spec, documents)
            output.append(
                {
                    **item,
                    "available_at": available.isoformat(),
                    "review_kind": "AI_SIMULATED",
                    "human_reviewed": False,
                    "case_sha256": receipt["case_sha256"],
                }
            )
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
            withheld += 1
    return {
        "items": output,
        "enabled": True,
        "withheld": withheld,
        "as_of": at.isoformat(),
        "delivery": "disabled",
    }
