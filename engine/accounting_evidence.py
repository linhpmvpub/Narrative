"""Exact-context Inline XBRL normalization for event-scoped accounting cases."""

import re
import xml.etree.ElementTree as ET
from datetime import date

from engine.filing_evidence import IX, XBRL, XD, number


def extract(document, *, cik, concept, start, end, dimensions=()):
    if len(document.encode()) > 5_000_000 or re.search(r"<!\s*(DOCTYPE|ENTITY)", document, re.I):
        raise ValueError("Unsafe/oversized XBRL")
    if not 1 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 370:
        raise ValueError("Invalid duration")
    try:
        root = ET.fromstring(document)
    except ET.ParseError:
        raise ValueError("Malformed XBRL") from None
    ids = [n.get("id") for n in root.iter() if n.get("id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate XBRL IDs")
    wanted = sorted(tuple(x) for x in dimensions)
    contexts = {}
    for node in root.iter("{" + XBRL + "}context"):
        ident = node.find(".//{" + XBRL + "}identifier")
        if (
            ident is None
            or ident.get("scheme") != "http://www.sec.gov/CIK"
            or (ident.text or "").zfill(10) != str(cik).zfill(10)
        ):
            continue
        if (
            node.findtext(".//{" + XBRL + "}startDate") != start
            or node.findtext(".//{" + XBRL + "}endDate") != end
        ):
            continue
        if (
            list(node.iter("{" + XD + "}typedMember"))
            or node.find("{" + XBRL + "}scenario") is not None
        ):
            continue
        dims = sorted((n.get("dimension"), n.text) for n in node.iter("{" + XD + "}explicitMember"))
        if dims == wanted:
            contexts[node.get("id")] = dims
    units = set()
    for n in root.iter("{" + XBRL + "}unit"):
        measures = list(n.iter("{" + XBRL + "}measure"))
        if (
            len(measures) == 1
            and measures[0].text == "iso4217:USD"
            and n.find("{" + XBRL + "}divide") is None
        ):
            units.add(n.get("id"))
    found = []
    for n in root.iter("{" + IX + "}nonFraction"):
        if (
            n.get("name") != concept
            or n.get("contextRef") not in contexts
            or n.get("unitRef") not in units
        ):
            continue
        value = number(n)
        found.append(
            {
                "value": str(value),
                "fact_id": n.get("id"),
                "context_id": n.get("contextRef"),
                "literal": "".join(n.itertext()),
                "scale": n.get("scale", "0"),
                "decimals": n.get("decimals"),
            }
        )
    if not found or len({x["value"] for x in found}) != 1:
        raise ValueError("Missing or conflicting exact-context facts")
    return {
        "value": found[0]["value"],
        "unit": "USD",
        "concept": concept,
        "start": start,
        "end": end,
        "dimensions": [list(x) for x in wanted],
        "basis": "GAAP",
        "provenance": found,
    }


def corroborate_companyfacts(payload, operand, accession, cik):
    if str(payload.get("cik")).zfill(10) != str(cik).zfill(10):
        raise ValueError("Companyfacts issuer mismatch")
    ns, tag = operand["concept"].split(":")
    rows = payload.get("facts", {}).get(ns, {}).get(tag, {}).get("units", {}).get("USD", [])
    matches = [
        (i, r)
        for i, r in enumerate(rows)
        if r.get("accn") == accession
        and r.get("start") == operand["start"]
        and r.get("end") == operand["end"]
        and r.get("form") in {"10-Q", "10-K"}
    ]
    if not matches or any(str(r["val"]) != operand["value"] for _, r in matches):
        raise ValueError("Companyfacts does not confirm exact filing/period/value")
    return {
        "status": "SAME_ISSUER_FILING_CROSSCHECK",
        "independent_causal_source": False,
        "json_pointers": [f"/facts/{ns}/{tag}/units/USD/{i}" for i, _ in matches],
    }


def comparable_periods(current, prior):
    cs, ce = (date.fromisoformat(current[k]) for k in ("start", "end"))
    ps, pe = (date.fromisoformat(prior[k]) for k in ("start", "end"))
    if not (
        350 <= (cs - ps).days <= 380
        and 350 <= (ce - pe).days <= 380
        and abs((ce - cs).days - (pe - ps).days) <= 7
    ):
        raise ValueError("Incompatible year-over-year periods")
    return {
        "comparison": "SAME_FILING_YEAR_OVER_YEAR",
        "current_days": (ce - cs).days + 1,
        "prior_days": (pe - ps).days + 1,
        "week_difference_retained": (ce - cs).days != (pe - ps).days,
    }
