"""Conservative shared source boundaries; never rewrite source text or offsets."""

import re

SPAN = re.compile(r"[\s\S]+")
LEGAL_SUFFIX = r"(?:Inc|Corp|Ltd|Co|plc)\."


def sentences(text):
    protected: set[int] = set()
    # Internal URL/email dots only; trailing punctuation remains a boundary.
    for match in re.finditer(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]+", text):
        end = match.end()
        while end > match.start() and text[end - 1] in ".!?;,)":
            end -= 1
        protected.update(range(match.start(), end))
    for match in re.finditer(r"\b(?:[A-Za-z]\.){2,}", text):
        protected.update(range(match.start(), match.end() - 1))
        tail = text[match.end():]
        if re.match(r"\s+[a-z]", tail):
            protected.add(match.end() - 1)
    for match in re.finditer(r"\b" + LEGAL_SUFFIX, text, re.I):
        if re.match(r"(?:\s*[,()]|\s+[a-z])", text[match.end():]):
            protected.add(match.end() - 1)
    start = 0
    for pos, char in enumerate(text):
        decimal = char == "." and pos > 0 and pos + 1 < len(text) and text[pos - 1].isdigit() and text[pos + 1].isdigit()
        if char not in ".!?;\n" or pos in protected or decimal:
            continue
        if chunk := SPAN.match(text, start, pos):
            yield chunk
        start = pos + 1
    if chunk := SPAN.match(text, start):
        yield chunk


def source_units(text):
    """Paragraph context accompanies, but never replaces, the literal sentence."""
    for sentence in sentences(text):
        if len(sentence.group()) <= 1600:
            yield {"summary": sentence.group(), "source_context": text,
                   "source_offset": sentence.start()}


def declared_reference(scope, text, start):
    """Only an explicit source alias, at most one preceding sentence, one hop.

    Pronouns and unquoted generic 'the company' have no inferred antecedent.
    Returned spans are relative to the unchanged paragraph/source field.
    """
    previous = [s for s in sentences(text[:start]) if s.group().strip()]
    begin = previous[-1].start() if previous else start
    prefix = text[begin:start]
    if len(prefix) > 1600 or "\n" in prefix or re.search(r"\b(but|whereas|while)\b", prefix, re.I):
        return None
    # Declarations inside this assertion are also eligible, but must precede use.
    current = next(sentences(text[start:]), None)
    end = start + current.end() if current else start
    context = text[begin:end]
    declarations = list(re.finditer(r'\(\s*(?:the\s+)?["“\'](?:the\s+)?(?P<alias>Company|Group)["”\']\s*\)', context, re.I))
    if len(declarations) != 1:
        return None
    declaration = declarations[0]
    names = "|".join(re.escape(t) for t in sorted(scope.subject_terms, key=len, reverse=True))
    antecedent = re.search(r"(?<!\w)(?P<name>" + names + r")(?!\w)(?:,?\s+" + LEGAL_SUFFIX + r")?\s*$",
                           context[:declaration.start()], re.I)
    if not antecedent:
        return None
    alias = "the " + declaration["alias"]
    usage_start = max(start, begin + declaration.end())
    usage = re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text[usage_start:end], re.I)
    if not usage:
        return None
    return {"alias": alias, "antecedent": {"start": begin + antecedent.start("name"),
            "end": begin + antecedent.end("name"), "text": antecedent["name"]},
            "declaration": {"start": begin + declaration.start(), "end": begin + declaration.end(),
                            "text": declaration.group()},
            "reference_span": {"start": usage_start + usage.start(), "end": usage_start + usage.end(),
                               "text": usage.group()},
            "offset_basis": "RELATIVE_TO_SOURCE_CONTEXT", "basis": "EXPLICIT_SOURCE_ALIAS_ONE_HOP"}
