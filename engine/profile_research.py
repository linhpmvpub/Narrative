"""Build local evidence workbooks for company-profile review, never active profiles."""

import argparse
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from engine.market_pipeline import save
from engine.news_articles import normalized_text

TERMS = {
    "identity": r"\b(incorporated|registrant|corporation|company name)\b",
    "products": r"\b(products|servers|processors|flash memory|solid.state|storage solutions)\b",
    "segments": r"\b(reportable segments?|business segments?)\b",
    "suppliers": r"\b(suppliers?|supply agreements?|foundries|manufacturing partners?)\b",
    "customers": r"\b(customers?|customer concentration)\b",
    "financials": r"\b(net revenue|net income|gross margin|cash flow|total debt)\b",
    "regulation": r"\b(export controls?|regulations?|export licenses?|tariffs?)\b",
    "capacity": r"\b(production capacity|manufacturing capacity|facilities|capacity expansion)\b",
    "markets": r"\b(geographic|geographical|international markets?|end.markets?)\b",
    "resilience": r"\b(disruptions?|business continuity|natural disasters?|shortages?)\b",
}


def build(manifest_path, output, policy, *, at=None):
    at = at or datetime.now(UTC)
    if at.tzinfo is None:
        raise ValueError("Aware review clock required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent.resolve()
    dossiers = []
    for ticker in policy["tickers"]:
        identity = manifest["identities"][ticker]
        cik = str(identity["cik"])
        if not re.fullmatch(r"[0-9]{10}", cik):
            raise ValueError("Invalid issuer CIK")
        filings = sorted(
            [
                f
                for f in manifest["filings"]
                if f["ticker"] == ticker and f["form"] in {"10-K", "10-Q"}
            ],
            key=lambda f: f["filing_date"],
            reverse=True,
        )[:2]
        components: dict[str, dict] = {
            k: {"status": "UNKNOWN", "candidates": [], "review_required": True}
            for k in policy["required_profile_components"]
        }
        sources = []
        for f in filings:
            path = (root / f["file"]).resolve()
            parsed = urlsplit(f["url"])
            retrieved = datetime.fromisoformat(f["retrieved_at"])
            if (
                not path.is_relative_to(root)
                or str(f["cik"]) != cik
                or parsed.scheme != "https"
                or parsed.hostname != "www.sec.gov"
                or not parsed.path.startswith(f"/Archives/edgar/data/{int(cik)}/")
                or retrieved.tzinfo is None
                or retrieved > at
                or date.fromisoformat(f["filing_date"]) > at.date()
                or (ticker == "SNDK" and date.fromisoformat(f["filing_date"]) < date(2025, 2, 21))
            ):
                raise ValueError("Filing identity, path or availability mismatch")
            raw = path.read_bytes()
            # Legacy SEC collector hashes decoded text and writes Windows newlines.
            # Validate that declared basis; retain a separate local-file byte hash.
            decoded = path.read_text(encoding="utf-8")
            if hashlib.sha256(decoded.encode()).hexdigest() != f["content_sha256"]:
                raise ValueError("Filing hash mismatch")
            text = normalized_text(raw)
            sha = hashlib.sha256(text.encode()).hexdigest()
            text_path = output / "texts" / (sha + ".txt")
            text_path.parent.mkdir(parents=True, exist_ok=True)
            if text_path.exists() and text_path.read_text(encoding="utf-8") != text:
                raise ValueError("Existing text capture corrupted")
            text_path.write_text(text, encoding="utf-8")
            sources.append(
                {
                    "url": f["url"],
                    "form": f["form"],
                    "filing_date": f["filing_date"],
                    "retrieved_at": f["retrieved_at"],
                    "decoded_source_sha256": f["content_sha256"],
                    "local_file_sha256": hashlib.sha256(raw).hexdigest(),
                    "text_sha256": sha,
                }
            )
            for component in components:
                for match in re.finditer(TERMS.get(component, r"(?!)"), text, re.I):
                    if len(components[component]["candidates"]) >= 3:
                        break
                    start = max(0, text.rfind(".", max(0, match.start() - 200), match.start()) + 1)
                    if match.start() - start > 200:
                        start = max(0, match.start() - 160)
                    end = min(len(text), match.end() + 380)
                    components[component]["candidates"].append(
                        {
                            "source_url": f["url"],
                            "decoded_source_sha256": f["content_sha256"],
                            "local_file_sha256": hashlib.sha256(raw).hexdigest(),
                            "text_sha256": sha,
                            "start": start,
                            "end": end,
                            "quote": text[start:end],
                            "status": "UNREVIEWED_KEYWORD_CONTEXT_NOT_ASSERTION",
                        }
                    )
        dossier = {
            "ticker": ticker,
            "cik": cik,
            "as_of": at.isoformat(),
            "components": components,
            "sources": sources,
            "status": "RESEARCH_DRAFT_NOT_ACTIVE_PROFILE",
            "relations": [],
            "unknowns": [
                "Attribution, reporting period, entity role and materiality require review"
            ],
            "graph_eligible": False,
            "delivery": "disabled",
        }
        save(output / (ticker + ".json"), dossier)
        dossiers.append(
            {
                "ticker": ticker,
                "sources": len(sources),
                "components_with_candidates": sum(
                    bool(c["candidates"]) for c in components.values()
                ),
                "sourced_components": 0,
                "active": False,
            }
        )
    result = {"companies": dossiers, "delivery": "disabled", "requires_source_review": True}
    save(output / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("config/product-v1.json"))
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.manifest, args.output, json.loads(args.policy.read_text(encoding="utf-8")))
        )
    )


if __name__ == "__main__":
    main()
