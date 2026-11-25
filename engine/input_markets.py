"""Small, sourced input/benchmark registry shared across company profiles."""

import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl

from engine.ingestion.contracts import digest
from engine.mechanism_scope import contains


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def source_text(raw):
    parser = Text()
    parser.feed(raw.decode("utf-8"))
    return " ".join(" ".join(parser.parts).split())


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Record):
    id: str
    url: HttpUrl
    file: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieved_at: AwareDatetime
    published_at: AwareDatetime | None = None
    status: Literal["CURRENT", "WITHDRAWN", "DISPUTED"]


class Evidence(Record):
    source_id: str
    quote: str = Field(min_length=1, max_length=8000)


class Commodity(Record):
    id: str
    label: str
    aliases: list[str] = Field(min_length=1, max_length=20)
    evidence: list[Evidence] = Field(min_length=1)


class Exposure(Record):
    id: str
    profile_id: str
    product_node_id: str
    product_label: str
    commodity_id: str
    input_label: str
    scope: str = Field(min_length=10)
    evidence: list[Evidence] = Field(min_length=1)
    # Only an explicitly documented use; no implicit industry-wide exposure.
    relation: Literal["USES_INPUT"] = "USES_INPUT"


class Market(Record):
    id: str
    commodity_id: str
    provider: str
    instrument: str
    basis: Literal["SPOT", "CONTRACT", "RETAIL", "INDEX"]
    currency: str | None = None
    unit: str | None = None
    geography: str | None = None
    evidence: list[Evidence] = Field(min_length=1)


class MarketLink(Record):
    id: str
    exposure_id: str
    market_id: str
    applicability: Literal["BENCHMARK_PROXY_ONLY"]
    limitations: str = Field(min_length=30)


class Registry(Record):
    schema_version: Literal["CORE_INPUT_MARKETS_V1"] = "CORE_INPUT_MARKETS_V1"
    version: int = Field(ge=1)
    atlas_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    known_at: AwareDatetime
    review_until: AwareDatetime
    reviewer_id: str = Field(min_length=1)
    reviewer_kind: Literal["HUMAN", "AI_OPERATOR"]
    sources: list[Source] = Field(min_length=1, max_length=100)
    commodities: list[Commodity] = Field(min_length=1, max_length=100)
    exposures: list[Exposure] = Field(min_length=1, max_length=500)
    markets: list[Market] = Field(max_length=100)
    market_links: list[MarketLink] = Field(max_length=500)
    delivery: Literal["disabled"] = "disabled"


def validate(registry, data, source_root, *, at=None):
    r = Registry.model_validate(registry)
    at = at or datetime.now(UTC)
    if (
        at.tzinfo is None
        or at > datetime.now(UTC)
        or r.atlas_sha256 != digest(data)
        or not datetime.fromisoformat(data["as_of"]) <= r.known_at <= at
        or not 0 < (r.review_until - r.known_at).total_seconds() <= 90 * 86400
    ):
        raise ValueError("Registry atlas/time mismatch")
    groups: list[list[Any]] = [r.sources, r.commodities, r.exposures, r.markets, r.market_links]
    if any(len({x.id for x in group}) != len(group) for group in groups):
        raise ValueError("Duplicate registry identity")
    root = Path(source_root).resolve()
    texts = {}
    for s in r.sources:
        path = (root / s.file).resolve()
        if (
            not path.is_relative_to(root)
            or Path(s.file).name != s.file
            or str(s.url).split(":")[0] != "https"
            or s.retrieved_at > r.known_at
            or (s.published_at and s.published_at > s.retrieved_at)
        ):
            raise ValueError("Invalid source path or chronology")
        raw = path.read_bytes()
        if len(raw) > 3_000_000 or hashlib.sha256(raw).hexdigest() != s.sha256:
            raise ValueError("Source capture changed")
        texts[s.id] = source_text(raw)

    def quotes(evidence):
        if any(e.source_id not in texts or e.quote not in texts[e.source_id] for e in evidence):
            raise ValueError("Evidence not in captured source")
        return " ".join(e.quote for e in evidence)

    aliases = set()
    commodities = {c.id: c for c in r.commodities}
    for c in r.commodities:
        text = quotes(c.evidence)
        for alias in c.aliases:
            if not alias.strip() or alias.casefold() in aliases or not contains(text, alias):
                raise ValueError("Ambiguous or unsourced commodity alias")
            aliases.add(alias.casefold())
    profiles = {p["id"]: p for p in data["profiles"]}
    nodes = {n["id"]: n for n in data["nodes"]}
    for e in r.exposures:
        text = quotes(e.evidence)
        n = nodes.get(e.product_node_id)
        if (
            e.profile_id not in profiles
            or not n
            or n["profile_id"] != e.profile_id
            or n["kind"] not in {"product", "segment", "facility"}
            or e.commodity_id not in commodities
            or not contains(text, e.product_label)
            or not contains(text, e.input_label)
            or e.input_label.casefold()
            not in {a.casefold() for a in commodities[e.commodity_id].aliases}
        ):
            raise ValueError("Exposure identity, scope or sourced input mismatch")
    markets = {m.id: m for m in r.markets}
    for m in r.markets:
        text = quotes(m.evidence)
        if (
            m.commodity_id not in commodities
            or not contains(text, m.instrument)
            or not contains(text.casefold(), m.basis.casefold())
            or any(v and not contains(text, v) for v in [m.currency, m.unit, m.geography])
        ):
            raise ValueError("Market instrument/basis/unit not grounded")
    exposures = {e.id: e for e in r.exposures}
    seen = set()
    for link in r.market_links:
        pair = (link.exposure_id, link.market_id)
        if (
            pair in seen
            or link.exposure_id not in exposures
            or link.market_id not in markets
            or exposures[link.exposure_id].commodity_id != markets[link.market_id].commodity_id
        ):
            raise ValueError("Incompatible or duplicate input/market link")
        seen.add(pair)
    return r


def route(r, commodity_id, *, market_id=None, at=None):
    """Use validated current registry; exact commodity IDs, never parent/sibling inference."""
    at = at or datetime.now(UTC)
    if not r.known_at <= at < r.review_until:
        return []
    current = {s.id for s in r.sources if s.status == "CURRENT"}

    def live(evidence):
        return all(e.source_id in current for e in evidence)

    commodity = next((c for c in r.commodities if c.id == commodity_id), None)
    if commodity is None or not live(commodity.evidence):
        return []
    markets = {m.id: m for m in r.markets if live(m.evidence)}
    rows = []
    for e in r.exposures:
        if e.commodity_id != commodity_id or not live(e.evidence):
            continue
        links = [
            link
            for link in r.market_links
            if link.exposure_id == e.id and link.market_id in markets
        ]
        if market_id and not any(link.market_id == market_id for link in links):
            continue
        rows.append(
            {
                "exposure": e.model_dump(mode="json"),
                "price_markets": [
                    {
                        "market": markets[link.market_id].model_dump(mode="json"),
                        "applicability": link.applicability,
                        "limitations": link.limitations,
                    }
                    for link in links
                ],
                "purchase_price_verified": False,
                "financial_magnitude": "UNKNOWN",
            }
        )
    return rows


def install(r, data, source_root, output):
    from engine.core_profile import project

    r = validate(r, data, source_root)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    (out / "sources").mkdir()
    for s in r.sources:
        shutil.copyfile(Path(source_root) / s.file, out / "sources" / s.file)
    payload = r.model_dump(mode="json")
    (out / "registry.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with sqlite3.connect(out / "registry.db") as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(
            "CREATE TABLE commodities(id TEXT PRIMARY KEY,payload TEXT); CREATE TABLE sources(id TEXT PRIMARY KEY,payload TEXT); CREATE TABLE exposures(id TEXT PRIMARY KEY,commodity_id TEXT REFERENCES commodities(id),payload TEXT); CREATE TABLE markets(id TEXT PRIMARY KEY,commodity_id TEXT REFERENCES commodities(id),payload TEXT); CREATE TABLE market_links(id TEXT PRIMARY KEY,exposure_id TEXT REFERENCES exposures(id),market_id TEXT REFERENCES markets(id),payload TEXT);"
        )
        for name in ["commodities", "sources"]:
            conn.executemany(
                f"INSERT INTO {name} VALUES (?,?)",
                [(x["id"], json.dumps(x)) for x in payload[name]],
            )
        for name in ["exposures", "markets"]:
            conn.executemany(
                f"INSERT INTO {name} VALUES (?,?,?)",
                [(x["id"], x["commodity_id"], json.dumps(x)) for x in payload[name]],
            )
        conn.executemany(
            "INSERT INTO market_links VALUES (?,?,?,?)",
            [
                (x["id"], x["exposure_id"], x["market_id"], json.dumps(x))
                for x in payload["market_links"]
            ],
        )
    (out / "core-profiles.json").write_text(
        json.dumps(project(data, r), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files = ["registry.json", "registry.db", "core-profiles.json"] + [
        "sources/" + s.file for s in r.sources
    ]
    (out / "manifest.json").write_text(
        json.dumps({n: hashlib.sha256((out / n).read_bytes()).hexdigest() for n in files}),
        encoding="utf-8",
    )
    return {
        "commodities": len(r.commodities),
        "exposures": len(r.exposures),
        "markets": len(r.markets),
        "market_links": len(r.market_links),
        "delivery": "disabled",
    }


def read(root, data):
    root = Path(root)
    raw = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    r = Registry.model_validate(raw)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    expected = {"registry.json", "registry.db", "core-profiles.json"} | {
        "sources/" + s.file for s in r.sources
    }
    if set(manifest) != expected:
        raise ValueError("Registry manifest mismatch")
    for name, sha in manifest.items():
        path = (root / name).resolve()
        if (
            not path.is_relative_to(root.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != sha
        ):
            raise ValueError("Registry artifact changed")
    return validate(r, data, root / "sources")


def main():
    import argparse

    from engine.impact_atlas import read_snapshot

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = read_snapshot(args.atlas)
    registry = Registry.model_validate_json(args.input.read_bytes())
    result = install(registry, data, args.sources, args.output)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
