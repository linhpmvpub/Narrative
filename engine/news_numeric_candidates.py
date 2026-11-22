"""Conservative candidates for one explicit quarterly earnings table layout."""

import re

from engine.news_articles import read_packet

TABLE = re.compile(
    r"(?P<basis>GAAP|Non-GAAP)\n\(\$ in (?P<scale>millions|billions), except earnings per share\)\n"
    r"(?P<current>Q[1-4] FY\d{2,4})\n(?P<previous>Q[1-4] FY\d{2,4})\n(?P<prior>Q[1-4] FY\d{2,4})\n"
    r"Q/Q\*?\nY/Y\*?\n(?P<metric>Revenue)\n\$(?P<value>[\d,]+(?:\.\d+)?)\n"
    r"\$(?P<previous_value>[\d,]+(?:\.\d+)?)\n\$(?P<prior_value>[\d,]+(?:\.\d+)?)(?:\n|$)"
)


def candidates(revision, packet_sha256):
    packet, text = read_packet(revision, packet_sha256)
    rows = []
    for match in TABLE.finditer(text):
        fields = {
            name: {"quote": match.group(name), "start": match.start(name), "end": match.end(name)}
            for name in TABLE.groupindex
        }
        rows.append(
            {
                "fields": fields,
                "source_span": {"start": match.start(), "end": match.end()},
                "source_quote": match.group(),
                "currency_symbol": "$",
                "currency": "UNKNOWN",
                "period_normalization": "UNRESOLVED",
                "scope": "UNVERIFIED",
                "status": "UNREVIEWED_EXTRACTION_CANDIDATE",
                "impact_eligible": False,
            }
        )
        if len(rows) == 10:
            break
    return {
        "parser": "EXPLICIT_QUARTERLY_REVENUE_TABLE_V1",
        "packet_sha256": packet_sha256,
        "source_url": packet["url"],
        "available_at": packet["retrieved_at"],
        "items": rows,
        "review_required": True,
        "delivery": "disabled",
        "limitations": [
            "Only this explicit table layout is supported; no matches is not no financial data.",
            "Currency, issuer, fiscal dates, duration, scope and accounting comparability require review.",
            "Repeated GAAP/non-GAAP figures are not independent corroboration.",
        ],
    }
