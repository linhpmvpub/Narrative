"""Bounded source discourse roles, separate from relevance and event truth.

Call only after a candidate has its own literal resource/asset evidence. A title
can establish editorial focus, never donate a missing actor, object or action.
"""

import re

from engine.source_sentences import sentences

VERSION = "source-role-v1"
BOUNDARY = r"[;!?\n]|\b(?:and|but|whereas|while)\b"
CONTINUITY = r"\b(?:has|have|had)\s+(?:(?:also|consistently|continuously)\s+)?(?:maintained|provided|offered|operated)\b"
HISTORY = r"\b(?:since\s+(?:(?:its\s+)?opening\s+in\s+)?\d{4}|for\s+(?:over\s+)?\d+\s+years)\b"
CAPABILITY = r"\b(?:(?:is|are)\s+(?:equipped|fitted)\s+with|speciali[sz]es?\s+in|(?:a|an)\s+(?:global\s+)?provider\s+of)\b"


def focused_title(headline, patterns):
    if not patterns:
        return False
    return any(all(re.search(pattern, clause, re.I) for pattern in patterns)
               for sentence in sentences(headline) for clause in re.split(BOUNDARY, sentence.group(), flags=re.I))


def assess(text, start, end, *, headline="", is_headline=False, focus_patterns=(), predicate_start=None):
    """Describe only the clause containing the independently matched anchors."""
    if not 0 <= start < end <= len(text):
        raise ValueError("Source role requires original candidate offsets")
    boundaries = list(re.finditer(BOUNDARY, text, re.I))
    left = max((m.end() for m in boundaries if m.end() <= start), default=0)
    right = min((m.start() for m in boundaries if m.start() >= end), default=len(text))
    clause = text[left:right]
    marker = re.search(CAPABILITY, clause, re.I)
    if predicate_start is not None:
        if not start <= predicate_start < end:
            raise ValueError("Predicate must occur within candidate evidence")
        # A capability must govern this action directly. An appositive describing
        # the operator cannot erase a separately stated new project decision.
        if marker and (left+marker.end() > predicate_start
                       or clause[marker.end():predicate_start-left].strip()):
            marker = None
    history = re.search(HISTORY, clause, re.I)
    continuity = re.search(CONTINUITY, clause, re.I)
    if (continuity and history and continuity.end() < history.start()
            and (predicate_start is None or left+continuity.end() <= predicate_start < left+history.end())):
        marker = continuity
    # A marker in another coordinated clause cannot suppress the candidate.
    descriptive = bool(marker and not re.search(BOUNDARY, clause, re.I))
    focused = is_headline or focused_title(headline, focus_patterns)
    role = "FOCUSED_DESCRIPTION" if descriptive and focused else "INCIDENTAL_DESCRIPTION" if descriptive else "OPERATING_OR_EXPLANATORY_CONTEXT"
    return {"version": VERSION, "role": role, "allowed": not descriptive or focused,
            "reason": "SOURCE_DESCRIPTION_WITH_PRIMARY_FOCUS" if descriptive and focused else
                      "PERSISTENT_OR_CAPABILITY_DESCRIPTION_WITHOUT_PRIMARY_FOCUS" if descriptive else
                      "NO_EXPLICIT_DESCRIPTIVE_MARKER",
            "headline_used_for_focus_only": bool(descriptive and focused and not is_headline),
            "clause_span": {"start": left, "end": right, "text": clause},
            "description_span": {"start": left+marker.start(), "end": left+marker.end(), "text": marker.group()} if descriptive and marker else None,
            "offset_basis": "RELATIVE_TO_SOURCE_WINDOW_TEXT", "financial_impact": "UNKNOWN"}
