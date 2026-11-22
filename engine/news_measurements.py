"""Source-span financial worksheets. Extraction candidates, never reviewed facts."""

import re
from decimal import Decimal
from typing import Literal

from pydantic import Field

from engine.ingestion.contracts import SourceSpan, StrictModel, digest
from engine.news_articles import read_packet


class Operand(StrictModel):
    value: SourceSpan
    period: SourceSpan
    unit: SourceSpan
    scale: SourceSpan
    concept: SourceSpan
    scope: SourceSpan
    accounting_basis: SourceSpan
    duration: SourceSpan


class Worksheet(StrictModel):
    packet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    ticker: Literal["MU", "NVDA", "AMD", "DELL", "SNDK"]
    issuer: SourceSpan
    current: Operand
    prior: Operand | None = None
    limitations: str = Field(min_length=20, max_length=4000)


ISSUERS = {
    "MU": "micron",
    "NVDA": "nvidia",
    "AMD": "advanced micro devices",
    "DELL": "dell",
    "SNDK": "sandisk",
}
SCALES = {
    "million": Decimal(1000000),
    "millions": Decimal(1000000),
    "billion": Decimal(1000000000),
    "billions": Decimal(1000000000),
    "thousand": Decimal(1000),
    "thousands": Decimal(1000),
}


def evaluate(revision, worksheet):
    packet, text = read_packet(revision, worksheet.packet_sha256)

    def quote(span):
        if span.end > len(text):
            raise ValueError("Source span exceeds article text")
        value = text[span.start : span.end]
        if not value.strip():
            raise ValueError("Empty source field")
        return value

    issuer = quote(worksheet.issuer)
    if not re.search(r"\b" + re.escape(ISSUERS[worksheet.ticker]) + r"\b", issuer, re.I):
        raise ValueError("Issuer not explicitly identified")
    if worksheet.ticker == "SNDK" and packet["retrieved_at"][:10] < "2025-02-21":
        raise ValueError("Sandisk predates separation")

    def operand(spec):
        fields = {k: quote(getattr(spec, k)) for k in Operand.model_fields}
        literal = fields["value"].strip()
        if not re.fullmatch(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", literal):
            raise ValueError("Ambiguous numeric literal")
        scale = fields["scale"].strip().casefold()
        if scale not in SCALES or fields["unit"].strip() not in {"USD", "US$", "U.S. dollars"}:
            raise ValueError("Explicit supported currency and scale required")
        return {
            "quotes": fields,
            "spans": spec.model_dump(),
            "literal_value": str(Decimal(literal.replace(",", ""))),
            "scaled_value": str(Decimal(literal.replace(",", "")) * SCALES[scale]),
            "currency": "USD",
        }

    current = operand(worksheet.current)
    prior = operand(worksheet.prior) if worksheet.prior else None
    change = None
    if prior:
        for key in ("unit", "concept", "scope", "accounting_basis", "duration"):
            if current["quotes"][key].strip().casefold() != prior["quotes"][key].strip().casefold():
                raise ValueError("Comparison scope or basis differs")
        if (
            current["quotes"]["period"].strip().casefold()
            == prior["quotes"]["period"].strip().casefold()
        ):
            raise ValueError("Distinct periods required")
        old, new = Decimal(prior["scaled_value"]), Decimal(current["scaled_value"])
        if old > 0:
            change = str(((new - old) / old * 100).quantize(Decimal("0.0001")))
    result = {
        "kind": "UNREVIEWED_FINANCIAL_WORKSHEET",
        "packet_sha256": worksheet.packet_sha256,
        "source_url": packet["url"],
        "available_at": packet["retrieved_at"],
        "ticker": worksheet.ticker,
        "issuer_quote": issuer,
        "current": current,
        "prior": prior,
        "arithmetic_change_percent": change,
        "comparison_validity": "REQUIRES_PERIOD_DURATION_AND_ACCOUNTING_REVIEW",
        "limitations": worksheet.limitations,
        "impact_eligible": False,
        "delivery": "disabled",
    }
    result["worksheet_sha256"] = digest(result)
    return result


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    from sqlalchemy import select

    from engine.db import database
    from engine.models.schema_v13 import news_revisions

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision_id")
    parser.add_argument("worksheet", type=Path)
    args = parser.parse_args()
    engine = database()
    try:
        with engine.connect() as conn:
            revision = (
                conn.execute(select(news_revisions).where(news_revisions.c.id == args.revision_id))
                .mappings()
                .one()
            )
            print(
                json.dumps(
                    evaluate(
                        revision,
                        Worksheet.model_validate_json(args.worksheet.read_text(encoding="utf-8")),
                    ),
                    indent=2,
                )
            )
    finally:
        engine.dispose()
