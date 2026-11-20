from datetime import date

from sqlalchemy import select
from sqlalchemy.engine import Connection

from engine.models.schema_v1 import metadata


def resolve_ticker(
    conn: Connection, symbol: str, on: date, *, require_verified: bool = True
) -> str | None:
    aliases = metadata.tables["rie_entity_aliases"]
    rows = conn.execute(select(aliases).where(aliases.c.symbol == symbol.upper())).mappings()
    matches = [
        row
        for row in rows
        if (row["effective_from"] is None or row["effective_from"] <= on)
        and (row["effective_until"] is None or on < row["effective_until"])
        and (not require_verified or row["external_id"] is not None)
    ]
    if len(matches) > 1:
        raise ValueError("Ambiguous ticker identity")
    return matches[0]["entity_id"] if matches else None


def validate_metric_issuer(issuer: str, metric: str, on: date) -> None:
    if metric.startswith("SNDK_") and (issuer != "CO_SNDK" or on < date(2025, 2, 21)):
        raise ValueError("SNDK requires post-separation issuer-specific financial provenance")
    for ticker in ("MU", "NVDA", "AMD", "DELL"):
        if metric.startswith(ticker + "_") and issuer != "CO_" + ticker:
            raise ValueError("Metric issuer mismatch")
