"""One-hop typed references in adjacent sentences of the same source paragraph.

Never concatenate headline/body, rewrite source text, infer an unnamed party's
identity, or resolve through another reference. Offsets retain original context.
"""

import re

from engine.source_sentences import sentences

VERSION = "typed-source-reference-v1"


def resolve(payload, field, text, start, antecedent, reference, candidates):
    context, offset = text, 0
    if field == "summary" and "source_offset" in payload:
        context, offset = payload.get("source_context", ""), payload["source_offset"]
        if (not isinstance(context, str) or type(offset) is not int or offset < 0
                or context[offset:offset+len(text)] != text):
            return None
    chunks = list(sentences(context))
    index = next((i for i, s in enumerate(chunks) if s.start() == offset+start), None)
    if index is None or index == 0:
        return None
    previous, current = chunks[index-1], chunks[index]
    prefix, value = previous.group(), current.group()
    if (len(prefix) > 1200 or len(value) > 1200
            or not re.fullmatch(r"\.\s*", context[previous.end():current.start()])
            or "\n" in context[previous.start():current.start()]
            or re.search(r"\b(?:and|but|whereas|while|no|not|never|without|denied|if|might|could|may|would|unless|rumou?r|hypothetical|cancel(?:s|led|ed)?|abandon(?:s|ed)?)\b", prefix, re.I)):
        return None
    targets = list(re.finditer(antecedent, prefix, re.I))
    uses = list(re.finditer(reference, value, re.I))
    # Count *all* competing candidates, not just the profile company's name.
    if len(targets) != 1 or len(uses) != 1 or len(list(re.finditer(candidates, prefix, re.I))) != 1:
        return None
    target, usage = targets[0], uses[0]
    return {"version": VERSION, "basis": "TYPED_ADJACENT_SOURCE_REFERENCE_ONE_HOP",
            "antecedent": {"start": previous.start()+target.start(), "end": previous.start()+target.end(), "text": target.group()},
            "reference_span": {"start": current.start()+usage.start(), "end": current.start()+usage.end(), "text": usage.group()},
            "window_span": {"start": current.start(), "end": current.end(), "text": value},
            "offset_basis": "RELATIVE_TO_SOURCE_CONTEXT", "identity_verified": False,
            "relationship_inferred": False}


def compute_party(payload, field, text, start, names):
    for role in ("buyers", "sellers", "customers"):
        named = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        result = resolve(payload, field, text, start,
            r"^\s*(?:"+named+r")(?:['’]s)?\s+(?:(?:GPU|chip|compute)\s+)?"+role+r"\b",
            r"^\s*(?:These|Those|The)\s+"+role+r"\b",
            r"\b(?:buyers|sellers|customers)\b")
        if result:
            return {**result, "kind": "COMPUTE_PARTY", "role": role.upper()}
    return None


def data_center(payload, field, text, start, *, subject_only=True):
    result = resolve(payload, field, text, start,
        r"\b(?:a|the|one|new)\s+data[ -]?cent(?:er|re)\b(?=\s*(?:$|,|\b(?:in|near|outside|with)\b))",
        (r"^\s*" if subject_only else r"\b")+r"(?:This|That|The)\s+(?:facility|site)\b",
        r"\b(?:data[ -]?cent(?:er|re)s?|facilit(?:y|ies)|sites?|plants?|factories)\b")
    return {**result, "kind": "DATA_CENTER_ASSET"} if result else None
