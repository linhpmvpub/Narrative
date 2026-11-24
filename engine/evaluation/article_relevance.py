"""Local full-body relevance experiment, separate from RSS/feed acceptance.

An operator selects the complete article body in integrity-checked visible HTML.
This is an explicit reviewed boundary, not an automatic completeness guarantee.
Manual public-document observations are not represented as RSS revisions.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from engine.adapters.news import canonical_url
from engine.company_profiles import available_bundles
from engine.evaluation.profile_relevance import overlaps, prior_exposure, shingles, write_new
from engine.ingestion.contracts import digest
from engine.news_articles import read_packet
from engine.profile_routing import binding_decisions


def utc(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if value.tzinfo is None:
        raise ValueError("Aware source timestamp required")
    return value.astimezone(UTC)


def reviewed_body(selection, at, *, article_root=None):
    if selection.get("provenance") != "MANUAL_PUBLIC_DOCUMENT_OBSERVATION_NOT_RSS":
        raise ValueError("Explicit manual document provenance required")
    revision = {**selection["revision"], "received_at": utc(selection["revision"]["received_at"])}
    packet, text = read_packet(revision, selection["packet_sha256"], root=article_root)
    if packet["relation"] != "same_article" or utc(packet["retrieved_at"]) > at:
        raise ValueError("Same article available before freeze required")
    review = selection["body_review"]
    start, end = review["start"], review["end"]
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
            or not 200 <= end - start <= 100_000
            or review.get("complete_body") is not True
            or not review.get("reviewer_id", "").strip()
            or not review.get("boundary_basis", "").strip()
            or not utc(packet["retrieved_at"]) <= utc(review["reviewed_at"]) <= at):
        raise ValueError("Complete body boundary review required")
    published = utc(revision["payload"]["published_at"])
    if published > utc(revision["received_at"]) or utc(revision["received_at"]) > at:
        raise ValueError("Publication/observation chronology invalid")
    body = text[start:end]
    exclusions = review.get("related_link_ranges", [])
    last = start
    for a, b in exclusions:
        if (type(a) is not int or type(b) is not int or not last <= a < b <= end
                or not text[a:b].startswith("Related:\n")
                or len(text[a:b].strip().splitlines()) != 2):
            raise ValueError("Only exact reviewed related-link blocks may be removed")
        last = b
    for a, b in reversed(exclusions):
        body = body[:a-start] + "\n" + body[b-start:]
    return packet, body


def full_body_decisions(bundle, narrative, title, body, at):
    """Route each paragraph separately; never assemble distant keyword groups.

    Paragraphs preserve line breaks from visible HTML. Conservative fragmentation
    can miss inline markup splits; traces expose that limitation.
    """
    for field, value in (("title", title), ("body", body)):
        offset = 0
        for paragraph in value.splitlines(keepends=True):
            # Headline and body cannot donate missing groups to one another.
            article = {"title": "", "summary": paragraph.rstrip("\r\n")}
            for decision in binding_decisions(bundle, narrative, article, at):
                yield {"binding_id": decision["binding"].id,
                       "scope": decision["binding"].scope,
                       "path": [edge.id for edge in decision["path"]],
                       "matches": [{**m, "field": field,
                                    "start": m["start"] + offset,
                                    "end": m["end"] + offset}
                                   for m in decision["matches"]]}
            offset += len(paragraph)


def freeze(selections, output: Path, *, exclude_packets=(), at=None):
    at = at or datetime.now(UTC)
    if at.tzinfo is None or at > datetime.now(UTC) or not 1 <= len(selections) <= 100:
        raise ValueError("Bounded selections and aware nonfuture cutoff required")
    registry = available_bundles(at)
    if not registry["enabled"] or registry.get("withheld") or registry.get("truncated"):
        raise ValueError("Complete validated profile registry required")
    bundles = registry["items"]
    prior, previous_texts, hashes = prior_exposure(exclude_packets)
    seen, packet, predictions, traces = set(), [], {}, {}
    texts: list[set[tuple[str, ...]]] = []
    excluded = 0
    for selection in selections:
        evidence, body = reviewed_body(selection, at)
        original = selection["revision"]["payload"]
        cluster = digest(canonical_url(original["url"]))
        article = {**original, "summary": body}
        tokens = shingles(article)
        if (cluster in prior or cluster in seen or overlaps(tokens, previous_texts)
                or overlaps(shingles(original), previous_texts) or overlaps(tokens, texts)):
            excluded += 1
            continue
        seen.add(cluster)
        texts.append(tokens)
        for bundle in bundles:
            for narrative in bundle.narratives:
                key = digest([cluster, bundle.id, bundle.version, narrative.id, "full_body_v1"])
                decisions = list(full_body_decisions(bundle, narrative, original["title"], body, at))
                predictions[key] = bool(decisions)
                traces[key] = decisions
                packet.append({"id": key, "cluster": cluster, "article": article,
                    "article_basis": "OPERATOR_REVIEWED_COMPLETE_BODY",
                    "source_observation": {"revision": selection["revision"],
                        "packet_sha256": selection["packet_sha256"],
                        "body_sha256": evidence["body_sha256"],
                        "text_sha256": evidence["text_sha256"],
                        "body_review": selection["body_review"],
                        "provenance": selection["provenance"]},
                    "profile_id": bundle.id, "profile_version": bundle.version,
                    "profile_sha256": digest(bundle.model_dump(mode="json")),
                    "ticker": bundle.ticker, "narrative": narrative.model_dump(mode="json"),
                    "sources": [s.model_dump(mode="json", exclude={"file"}) for s in bundle.sources],
                    "components": [c.model_dump() for c in bundle.components],
                    "nodes": [n.model_dump() for n in bundle.nodes],
                    "relationships": [r.model_dump(mode="json") for r in bundle.relationships]})
    if not packet:
        raise ValueError("No unseen complete articles")
    current = available_bundles(at)
    if (current.get("withheld") or current.get("truncated") or not current["enabled"]
            or digest([b.model_dump(mode="json") for b in current["items"]])
            != digest([b.model_dump(mode="json") for b in bundles])):
        raise ValueError("Registry changed during freeze")
    receipt = {"at": at.isoformat(), "packet_sha256": digest(packet),
        "predictions_sha256": digest(predictions), "traces_sha256": digest(traces),
        "prediction_track": "full_article_relevance", "clusters": len(seen),
        "pairs": len(packet), "excluded_exposure_or_duplicates": excluded,
        "prior_packet_sha256": hashes, "selection_sha256": digest(selections),
        "sampling": "CURATED_UNSEEN_DOCUMENTS_NOT_RANDOM_MARKET_SAMPLE",
        "scope": "Current profiles on complete body; not historical as-of or feed eligibility",
        "delivery": "disabled", "independent_gold": False}
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("packet", packet), ("predictions", predictions),
                        ("traces", traces), ("selections", selections), ("freeze", receipt)):
        write_new(output / (name + ".json"), value)
    return receipt


def verify_frozen(directory, packet, receipt):
    selections = json.loads((directory / "selections.json").read_text(encoding="utf-8"))
    traces = json.loads((directory / "traces.json").read_text(encoding="utf-8"))
    if (digest(selections) != receipt["selection_sha256"]
            or digest(traces) != receipt["traces_sha256"]
            or set(traces) != {row["id"] for row in packet}):
        raise ValueError("Frozen full article artifacts changed")
    at = utc(receipt["at"])
    checked = {}
    for row in packet:
        observation = row["source_observation"]
        key = digest(observation)
        if key not in checked:
            _, checked[key] = reviewed_body(observation, at)
        if row["article"]["summary"] != checked[key]:
            raise ValueError("Frozen body differs from reviewed source")


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selections", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--exclude-packet", type=Path, action="append", default=[])
    args = parser.parse_args()
    selections = json.loads(args.selections.read_text(encoding="utf-8"))
    print(json.dumps(freeze(selections, args.directory, exclude_packets=args.exclude_packet), indent=2))


if __name__ == "__main__":
    main()
