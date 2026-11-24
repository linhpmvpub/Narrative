"""Local dependency-parser experiment. Syntax proposals never authorize impact cards."""

import argparse
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path


def sha(value):
    return hashlib.sha256(value).hexdigest()


def span(text, start, end):
    if not 0 <= start < end <= len(text):
        raise ValueError("Invalid source span")
    return {"start": start, "end": end, "text": text[start:end]}


def propose(text, tokens):
    """Consume dependency annotations; retain uncertainty rather than assert truth.

    Heads index this block's token array. Subjects are never borrowed across verbs,
    sentences or documents. No financial vocabulary/issuer-specific rules are used.
    """
    if not isinstance(text, str) or len(text) > 100_000 or len(tokens) > 25_000:
        raise ValueError("Bounded block required")
    children: dict[int, list[int]] = {i: [] for i in range(len(tokens))}
    previous = 0
    for i, token in enumerate(tokens):
        a, b, head = token["start"], token["end"], token["head"]
        if (
            not 0 <= head < len(tokens)
            or not previous <= a < b <= len(text)
            or text[a:b] != token["text"]
            or not 0 <= token["sentence_start"] <= a < b <= token["sentence_end"] <= len(text)
        ):
            raise ValueError("Invalid token/source alignment")
        previous = b
        if head != i:
            if (tokens[head]["sentence_start"], tokens[head]["sentence_end"]) != (
                token["sentence_start"],
                token["sentence_end"],
            ):
                raise ValueError("Cross-sentence dependency")
            children[head].append(i)
    # Reject cycles even in subtrees that do not become candidates, in linear time.
    done = set()
    for i in range(len(tokens)):
        visited = set()
        node = i
        while node not in done and tokens[node]["head"] != node:
            if node in visited:
                raise ValueError("Cyclic dependency")
            visited.add(node)
            node = tokens[node]["head"]
        done.update(visited | {node})
    sentences: dict[int, list[dict]] = {}
    for token in tokens:
        sentences.setdefault(token["sentence_start"], []).append(token)

    def phrase(index):
        todo, indices = [index], []
        while todo:
            node = todo.pop()
            indices.append(node)
            todo.extend(children[node])
        a, b = min(indices), max(indices)
        if sorted(indices) != list(range(a, b + 1)):
            return None
        return span(text, tokens[a]["start"], tokens[b]["end"])

    candidates, audit = [], []
    for i, token in enumerate(tokens):
        if token["pos"] != "VERB":
            continue
        sentence = span(text, token["sentence_start"], token["sentence_end"])
        local = sentences[token["sentence_start"]]
        direct = children[i]
        subjects = [j for j in direct if tokens[j]["dep"] == "nsubj"]
        objects = [j for j in direct if tokens[j]["dep"] in {"dobj", "obj"}]
        patients = [j for j in direct if tokens[j]["dep"] == "nsubjpass"]
        agents = [
            k
            for j in direct
            if tokens[j]["dep"] == "agent"
            for k in children[j]
            if tokens[k]["dep"] == "pobj"
        ]
        voice = "PASSIVE" if patients else "ACTIVE"
        if patients:
            subjects, objects = agents, patients
        if len(subjects) != 1 or len(objects) != 1:
            audit.append(
                {
                    "predicate": span(text, token["start"], token["end"]),
                    "sentence": sentence,
                    "reason": "UNRESOLVED_EXPLICIT_ROLES",
                }
            )
            continue
        actor, obj = phrase(subjects[0]), phrase(objects[0])
        if actor is None or obj is None:
            audit.append({"sentence": sentence, "reason": "DISCONTIGUOUS_ROLE"})
            continue
        flags = []
        words = {t["text"].casefold() for t in local}
        if any(t["dep"] == "neg" for t in local) or words & {"no", "neither", "without", "never"}:
            flags.append("NEGATION_IN_SENTENCE")
        if words & {"if", "unless", "may", "might", "could", "would"}:
            flags.append("CONDITIONAL_OR_MODAL")
        if any(t["dep"] in {"ccomp", "xcomp", "parataxis"} for t in local) or any(
            c in sentence["text"] for c in ['"', "“", "”"]
        ):
            flags.append("EMBEDDED_OR_ATTRIBUTED_CLAIM")
        if tokens[subjects[0]]["pos"] == "PRON":
            flags.append("UNRESOLVED_ACTOR_REFERENCE")
        if any(t["dep"] == "conj" for t in local):
            flags.append("COORDINATION_REQUIRES_REVIEW")
        phase = "UNKNOWN"
        if words & {"will", "shall"}:
            phase = "PROPOSED"
        elif not flags and token["tag"] == "VBD":
            phase = "REPORTED_ACTION"
        contexts = [
            span(text, t["start"], t["end"]) | {"entity_type": t["entity"]}
            for t in local
            if t.get("entity") in {"DATE", "TIME", "MONEY", "PERCENT", "QUANTITY"}
        ]
        candidates.append(
            {
                "id": sha(json.dumps([sentence, token["start"]], sort_keys=True).encode()),
                "sentence": sentence,
                "actor": actor,
                "object": obj,
                "predicate": span(text, token["start"], token["end"]),
                "predicate_lemma": token["lemma"],
                "voice": voice,
                "phase": phase,
                "review_flags": flags,
                "context_tokens": contexts,
                "occurrence_time": None,
                "status": "SYNTAX_PROPOSAL_REQUIRES_REVIEW",
                "identity": "UNRESOLVED",
                "mechanism": "UNKNOWN",
                "strength": "UNKNOWN",
                "horizon": "UNKNOWN",
                "delivery": "disabled",
            }
        )
    return candidates, audit


def export_blocks(selections, article_root, at):
    from engine.article_cards import substantive_blocks

    if not 1 <= len(selections) <= 100 or at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Bounded selections/nonfuture cutoff required")
    records, seen = [], set()
    for selection in selections:
        key = sha(json.dumps(selection, sort_keys=True).encode())
        if key in seen:
            continue
        seen.add(key)
        blocks, suppressed = substantive_blocks(selection, at, article_root=article_root)
        records.append(
            {
                "selection_sha256": key,
                "packet_sha256": selection["packet_sha256"],
                "source_url": selection["revision"]["payload"]["url"],
                "blocks": blocks,
                "suppressed_blocks": len(suppressed),
            }
        )
    return {
        "schema": "reviewed-extraction-input-v1",
        "as_of": at.isoformat(),
        "documents": records,
        "delivery": "disabled",
        "historical_as_of": False,
    }


def run_model(packet, nlp):
    if (
        packet.get("schema") != "reviewed-extraction-input-v1"
        or not 1 <= len(packet["documents"]) <= 100
    ):
        raise ValueError("Reviewed bounded input packet required")
    rows = []
    total = 0
    for document in packet["documents"]:
        for index, block in enumerate(document["blocks"]):
            text = block["text"]
            total += len(text)
            if len(text) > 100_000 or total > 2_000_000:
                raise ValueError("Input size exceeded")
            doc = nlp(text)
            tokens = [
                {
                    "start": t.idx,
                    "end": t.idx + len(t.text),
                    "text": t.text,
                    "head": t.head.i,
                    "dep": t.dep_,
                    "pos": t.pos_,
                    "tag": t.tag_,
                    "lemma": t.lemma_,
                    "entity": t.ent_type_,
                    "sentence_start": t.sent.start_char,
                    "sentence_end": t.sent.end_char,
                }
                for t in doc
            ]
            candidates, audit = propose(text, tokens)
            rows.append(
                {
                    "selection_sha256": document["selection_sha256"],
                    "packet_sha256": document["packet_sha256"],
                    "block": index,
                    "source_spans": block["source_spans"],
                    "source_block": text,
                    "candidates": candidates,
                    "audit": audit,
                }
            )
    return {
        "schema": "dependency-review-queue-v1",
        "rows": rows,
        "delivery": "disabled",
        "active_feed_changed": False,
        "source_status": "EXPORTED_SNAPSHOT_REQUIRES_REVALIDATION_BEFORE_USE",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "extract"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--articles", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    if len(raw) > 20_000_000:
        raise ValueError("Input file too large")
    packet = json.loads(raw)
    if args.action == "export":
        if args.articles is None:
            parser.error("--articles required for export")
        result = export_blocks(packet, args.articles, datetime.now(UTC))
    else:
        import spacy

        if spacy.__version__ != "3.8.11":
            raise ValueError("Pinned spaCy3.8.11 required")
        nlp = spacy.load("en_core_web_sm")
        if nlp.meta["version"] != "3.8.0":
            raise ValueError("Pinned model3.8.0 required")
        result = run_model(packet, nlp)
        model_root = Path(nlp.path)
        result["model_files"] = {
            p.relative_to(model_root).as_posix(): sha(p.read_bytes())
            for p in sorted(model_root.rglob("*"))
            if p.is_file()
        }
        result["packages"] = dict(
            sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
        )
        result["input_sha256"] = sha(raw)
        result["extractor_sha256"] = sha(Path(__file__).read_bytes())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"output": str(args.output), "delivery": "disabled"}))


if __name__ == "__main__":
    main()
