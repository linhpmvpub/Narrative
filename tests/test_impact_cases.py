"""Synthetic accounting regressions; real worked-case evidence stays private."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_product import client as client
from test_product import headers
from test_product import identities as identities

from engine.accounting_evidence import comparable_periods
from engine.impact_cases import build, case_feed
from engine.ingestion.contracts import digest


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_INFORMATIONAL_FEED", "true")
    monkeypatch.setenv("IMPACT_CASE_ROOT", str(tmp_path))
    root = tmp_path / "synthetic"
    root.mkdir()
    context = '<x:context id="c"><x:entity><x:identifier scheme="http://www.sec.gov/CIK">0001045810</x:identifier></x:entity><x:period><x:startDate>2025-01-27</x:startDate><x:endDate>2025-04-27</x:endDate></x:period></x:context>'
    charge = context.replace('id="c"', 'id="q"').replace(
        "</x:entity>",
        '<x:segment><d:explicitMember dimension="us-gaap:NatureOfExpenseAxis">nvda:H20ProductExcessInventoryAndPurchaseObligationsMember</d:explicitMember></x:segment></x:entity>',
    )
    facts = "".join(
        f'<ix:nonFraction id="f{i}" name="us-gaap:{tag}" contextRef="{ctx}" unitRef="usd" scale="6" decimals="-6">{value}</ix:nonFraction>'
        for i, (tag, ctx, value) in enumerate(
            [
                ("Revenues", "c", 100),
                ("GrossProfit", "c", 60),
                ("CostOfRevenue", "c", 40),
                ("CostOfRevenue", "q", 10),
            ]
        )
    )
    document = f'<html xmlns:x="http://www.xbrl.org/2003/instance" xmlns:d="http://xbrl.org/2006/xbrldi" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><p>Synthetic charge attributable to test event.</p>{context}{charge}<x:unit id="usd"><x:measure>iso4217:USD</x:measure></x:unit>{facts}</html>'
    payload = {
        "cik": 1045810,
        "facts": {
            "us-gaap": {
                tag: {
                    "units": {
                        "USD": [
                            {
                                "val": value * 1000000,
                                "start": "2025-01-27",
                                "end": "2025-04-27",
                                "accn": "0001045810-25-000116",
                                "form": "10-Q",
                            }
                        ]
                    }
                }
                for tag, value in [("Revenues", 100), ("GrossProfit", 60), ("CostOfRevenue", 40)]
            }
        },
    }
    docs = {"filing": document, "facts": json.dumps(payload)}
    urls = {
        "filing": "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000116/test.htm",
        "facts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json",
    }
    sources = {}
    for name, text in docs.items():
        data = text.encode()
        (root / (name + ".txt")).write_bytes(data)
        sources[name] = {
            "file": name + ".txt",
            "url": urls[name],
            "sha256": hashlib.sha256(data).hexdigest(),
            "retrieved_at": (datetime.now(UTC) - timedelta(minutes=2)).isoformat(),
        }
    spec = {
        "id": "synthetic",
        "ticker": "NVDA",
        "title": "Synthetic case",
        "cik": "0001045810",
        "accession": "0001045810-25-000116",
        "start": "2025-01-27",
        "end": "2025-04-27",
        "sources": sources,
        "mechanism_quote": "Synthetic charge attributable to test event.",
        "limitations": ["Synthetic only"],
        "operands": {
            "revenue": {"concept": "us-gaap:Revenues"},
            "gross_profit": {"concept": "us-gaap:GrossProfit"},
            "cost_of_revenue": {"concept": "us-gaap:CostOfRevenue"},
            "charge": {
                "concept": "us-gaap:CostOfRevenue",
                "dimensions": [
                    [
                        "us-gaap:NatureOfExpenseAxis",
                        "nvda:H20ProductExcessInventoryAndPurchaseObligationsMember",
                    ]
                ],
            },
        },
    }
    data = json.dumps(spec).encode()
    (root / "case.json").write_bytes(data)
    receipt = {
        "status": "active",
        "available_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "case_sha256": hashlib.sha256(data).hexdigest(),
        "reviews": [],
    }
    for role in ["retail", "fund", "expert"]:
        data = json.dumps(
            {
                "role": role,
                "input_sha256": digest(spec),
                "verdict": "ACCEPT_REPORTED_ACCOUNTING_CASE",
                "reviewer_kind": "AI_SIMULATED",
            }
        ).encode()
        name = role + ".json"
        (root / name).write_bytes(data)
        receipt["reviews"].append({"file": name, "sha256": hashlib.sha256(data).hexdigest()})
    (root / "receipt.json").write_text(json.dumps(receipt))
    return root, spec, docs


def test_accounting_case_scope_and_no_price_inference(case):
    _, spec, docs = case
    result = build(spec, docs)
    assert result["recognized_charge_usd"] == "10000000"
    assert result["reported_gross_margin_percent"] == "60.00"
    assert result["conditional_margin_drag_pp"] == "10.00"
    assert result["stock_price_impact"] == "UNKNOWN"
    assert not result["general_graph_eligible"]
    assert result["crosschecks"]["revenue"]["independent_causal_source"] is False
    assert len(case_feed()["items"]) == 1
    assert case_feed(datetime.now(UTC) - timedelta(days=1))["items"] == []


@pytest.mark.parametrize(
    "mutation", ["unit", "issuer", "period", "dimension", "conflict", "entity", "malformed"]
)
def test_exact_context_rejects_ambiguous_facts(case, mutation):
    _, spec, docs = case
    document = docs["filing"]
    if mutation == "unit":
        document = document.replace("iso4217:USD", "iso4217:EUR")
    if mutation == "issuer":
        document = document.replace("0001045810", "0000000001")
    if mutation == "period":
        document = document.replace("2025-01-27", "2024-01-27")
    if mutation == "dimension":
        document = document.replace(
            "nvda:H20ProductExcessInventoryAndPurchaseObligationsMember", "nvda:Other"
        )
    if mutation == "conflict":
        document = document.replace(
            "</html>",
            '<ix:nonFraction id="conflict" name="us-gaap:Revenues" contextRef="c" unitRef="usd" scale="6">101</ix:nonFraction></html>',
        )
    if mutation == "entity":
        document = '<!DOCTYPE html [<!ENTITY x "attack">]>' + document
    if mutation == "malformed":
        document = "<broken"
    with pytest.raises(ValueError):
        build(spec, {**docs, "filing": document})


@pytest.mark.parametrize("target", ["filing.txt", "facts.txt", "retail.json", "case.json"])
def test_case_tamper_withheld(case, target):
    root, _, _ = case
    (root / target).write_bytes(b"tampered")
    assert case_feed()["items"] == []


def test_case_withdrawal_and_scope_mismatch(case):
    root, spec, docs = case
    p = root / "receipt.json"
    r = json.loads(p.read_text())
    r["status"] = "withdrawn"
    p.write_text(json.dumps(r))
    assert case_feed()["items"] == []
    bad = deepcopy(spec)
    bad["sources"]["filing"]["url"] = "https://www.sec.gov/wrong"
    with pytest.raises(ValueError, match="identity"):
        build(bad, docs)
    facts = json.loads(docs["facts"])
    facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = 101000000
    with pytest.raises(ValueError, match="confirm"):
        build(spec, {**docs, "facts": json.dumps(facts)})


def test_comparable_quarter_rejects_ytd():
    assert (
        comparable_periods(
            {"start": "2025-01-27", "end": "2025-04-27"},
            {"start": "2024-01-29", "end": "2024-04-28"},
        )["current_days"]
        == 91
    )
    with pytest.raises(ValueError):
        comparable_periods(
            {"start": "2025-01-27", "end": "2025-07-27"},
            {"start": "2024-04-29", "end": "2024-07-28"},
        )


def test_impact_case_api_private(client, identities, case):
    assert client.get("/api/v0/news/impact-cases").status_code == 401
    response = client.get("/api/v0/news/impact-cases", headers=headers(identities[0]))
    assert response.status_code == 200 and len(response.json()["items"]) == 1
    assert "no-store" in response.headers["cache-control"]
    assert "reviews" not in response.json()["items"][0]
    from engine.mobile_gateway import allowed

    assert allowed("GET", "/api/v0/news/impact-cases")
    assert not allowed("POST", "/api/v0/news/impact-cases")


def test_case_identity_and_role_gate(case):
    root, spec, docs = case
    bad = deepcopy(spec)
    bad["ticker"] = "MU"
    with pytest.raises(ValueError, match="issuer"):
        build(bad, docs)
    p = root / "receipt.json"
    receipt = json.loads(p.read_text())
    receipt["reviews"][2] = receipt["reviews"][1]
    p.write_text(json.dumps(receipt))
    assert case_feed()["items"] == []
