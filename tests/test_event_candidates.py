"""Hand-annotated synthetic syntax; not pretrained-model accuracy tests."""

import copy
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from test_article_relevance import selection as selection

from engine.event_candidates import export_blocks, propose, span
from engine.product_scope import NodeRange, Scope, ScopeAnnotation, compare


def parsed(words, heads, deps, poses=None):
    text = " ".join(words)
    tokens, offset = [], 0
    for i, word in enumerate(words):
        tokens.append(
            {
                "text": word,
                "start": offset,
                "end": offset + len(word),
                "head": heads[i],
                "dep": deps[i],
                "pos": poses[i] if poses else ("VERB" if deps[i] == "ROOT" else "NOUN"),
                "lemma": word.lower(),
                "tag": "VBD",
                "entity": "",
                "sentence_start": 0,
                "sentence_end": len(text),
            }
        )
        offset += len(word) + 1
    return text, tokens


def active():
    return parsed(
        ["Alpha", "expanded", "wafer", "production"],
        [1, 1, 3, 1],
        ["nsubj", "ROOT", "compound", "dobj"],
    )


def test_source_roles_active():
    text, tokens = active()
    events, audit = propose(text, tokens)
    assert not audit and len(events) == 1
    e = events[0]
    assert e["actor"]["text"] == "Alpha" and e["object"]["text"] == "wafer production"
    assert e["phase"] == "REPORTED_ACTION" and e["mechanism"] == "UNKNOWN"
    assert e["delivery"] == "disabled" and e["identity"] == "UNRESOLVED"
    for key in ["actor", "object", "predicate", "sentence"]:
        assert text[e[key]["start"] : e[key]["end"]] == e[key]["text"]


def test_passive_roles_and_no_invented_agent():
    text, tokens = parsed(
        ["Factories", "were", "built", "by", "Alpha"],
        [2, 2, 2, 2, 3],
        ["nsubjpass", "auxpass", "ROOT", "agent", "pobj"],
    )
    e = propose(text, tokens)[0][0]
    assert e["voice"] == "PASSIVE" and e["actor"]["text"] == "Alpha"
    assert e["object"]["text"] == "Factories"
    tokens[-1]["dep"] = "dep"
    events, audit = propose(text, tokens)
    assert not events and audit[0]["reason"] == "UNRESOLVED_EXPLICIT_ROLES"


@pytest.mark.parametrize(
    "marker,dep,flag",
    [
        ("not", "neg", "NEGATION_IN_SENTENCE"),
        ("might", "aux", "CONDITIONAL_OR_MODAL"),
        ("if", "mark", "CONDITIONAL_OR_MODAL"),
        ("never", "advmod", "NEGATION_IN_SENTENCE"),
    ],
)
def test_uncertainty_preserved(marker, dep, flag):
    text, tokens = parsed(
        ["Alpha", marker, "expanded", "production"], [2, 2, 2, 2], ["nsubj", dep, "ROOT", "dobj"]
    )
    e = propose(text, tokens)[0][0]
    assert flag in e["review_flags"] and e["phase"] == "UNKNOWN"


def test_future_and_pronoun_require_review():
    text, tokens = parsed(
        ["They", "will", "expand", "production"],
        [2, 2, 2, 2],
        ["nsubj", "aux", "ROOT", "dobj"],
        ["PRON", "AUX", "VERB", "NOUN"],
    )
    e = propose(text, tokens)[0][0]
    assert e["phase"] == "PROPOSED" and "UNRESOLVED_ACTOR_REFERENCE" in e["review_flags"]


@pytest.mark.parametrize("fault", ["text", "offset", "head", "cycle", "sentence"])
def test_invalid_annotations_rejected(fault):
    text, tokens = active()
    tokens = copy.deepcopy(tokens)
    if fault == "text":
        tokens[0]["text"] = "Beta"
    elif fault == "offset":
        tokens[0]["end"] = len(text) + 1
    elif fault == "head":
        tokens[0]["head"] = 100
    elif fault == "cycle":
        tokens[1]["head"] = 0
    else:
        tokens[1]["sentence_start"] = 1
    with pytest.raises(ValueError):
        propose(text, tokens)


def test_bound_and_empty():
    assert propose("", []) == ([], [])
    with pytest.raises(ValueError):
        propose("x" * 100001, [])
    with pytest.raises(ValueError):
        span("abc", 2, 4)


def scope(**kwargs):
    return Scope.model_validate(
        {
            "vocabulary_sha256": "a" * 64,
            "products": ["cpu", "gpu"],
            "materials": ["wafer"],
            "geographies": ["TW"],
            "process_nm": {"lower": 0, "upper": 7},
            **kwargs,
        }
    )


def test_scope_subset_not_impact_authority():
    result = compare(scope(products=["gpu"], process_nm={"lower": 3, "upper": 3}), scope())
    assert result["relation"] == "NARROWER" and not result["impact_authorized"]
    assert compare(scope(), scope())["relation"] == "EXACT"
    assert compare(scope(), scope(products=["cpu"]))["relation"] == "BROADER"
    assert compare(scope(products=["nand"]), scope())["relation"] == "DISJOINT"


def test_scope_unknown_not_universal():
    result = compare(scope(products=None, process_nm=None), scope())
    assert result["relation"] == "UNKNOWN"
    assert result["dimensions"]["materials"] == "EXACT"
    assert compare(scope(products=None), scope(products=None))["relation"] == "UNKNOWN"
    assert compare(scope(products=None, geographies=["US"]), scope())["relation"] == "DISJOINT"


def test_process_endpoint_and_crossed_dimensions():
    assert (
        compare(scope(process_nm={"lower": 7, "lower_inclusive": False}), scope())["relation"]
        == "DISJOINT"
    )
    assert compare(scope(process_nm={"lower": 7}), scope())["relation"] == "PARTIAL_OVERLAP"
    result = compare(scope(products=["cpu"], geographies=["TW", "US"]), scope())
    assert result["relation"] == "PARTIAL_OVERLAP"


@pytest.mark.parametrize(
    "data",
    [
        {"lower": 8, "upper": 7},
        {"lower": 7, "upper": 7, "upper_inclusive": False},
        {"lower": "NaN"},
        {"lower": -1},
    ],
)
def test_invalid_node_ranges(data):
    with pytest.raises(ValueError):
        NodeRange.model_validate(data)


def test_vocabulary_and_empty_scope_rejected():
    with pytest.raises(ValueError):
        compare(scope(vocabulary_sha256="b" * 64), scope())
    with pytest.raises(ValueError):
        scope(products=[])


def test_annotation_is_source_bound_not_semantic_proof():
    text = "Synthetic wafers for CPU and GPU."
    a = ScopeAnnotation(
        scope=scope(),
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        start=0,
        end=len(text),
        quote=text,
        reviewer_id="test",
        reviewer_kind="AI_OPERATOR",
        interpretation_status="REVIEWER_DECLARED_NOT_INDEPENDENT_GOLD",
    )
    a.check_source(text)
    with pytest.raises(ValueError):
        a.check_source(text.replace("CPU", "NAND"))


def test_export_uses_reviewed_body_and_excludes_navigation(selection):
    packet = export_blocks([selection, selection], None, datetime.now(UTC))
    assert len(packet["documents"]) == 1
    body = " ".join(b["text"] for b in packet["documents"][0]["blocks"])
    assert "Related:" not in body and "Other news" not in body
    assert "Server memory prices fall." in body
    assert packet["delivery"] == "disabled" and not packet["historical_as_of"]


@pytest.mark.parametrize("fault", ["hash", "incomplete", "future"])
def test_export_preserves_source_review_gates(selection, fault):
    s = copy.deepcopy(selection)
    if fault == "hash":
        s["packet_sha256"] = "0" * 64
    elif fault == "incomplete":
        s["body_review"]["complete_body"] = False
    else:
        s["body_review"]["reviewed_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    with pytest.raises((ValueError, FileNotFoundError)):
        export_blocks([s], None, datetime.now(UTC))
