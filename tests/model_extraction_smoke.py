"""Run explicitly in isolated pinned NLP environment; synthetic cases, not market gold."""

import json

import spacy

from engine.event_candidates import run_model


def main():
    assert spacy.__version__ == "3.8.11"
    nlp = spacy.load("en_core_web_sm")
    assert nlp.meta["version"] == "3.8.0"
    cases = [
        ("Alpha built factories.", "ACTIVE", None),
        ("Alpha will build factories.", "ACTIVE", None),
        ("Factories were built by Alpha.", "PASSIVE", None),
        ("Alpha did not build factories.", "ACTIVE", "NEGATION_IN_SENTENCE"),
        ("Alpha might build factories.", "ACTIVE", "CONDITIONAL_OR_MODAL"),
        ("They built factories.", "ACTIVE", "UNRESOLVED_ACTOR_REFERENCE"),
        ("Beta said Alpha built factories.", "ACTIVE", "EMBEDDED_OR_ATTRIBUTED_CLAIM"),
        ("If Alpha built factories, demand would increase.", "ACTIVE", "CONDITIONAL_OR_MODAL"),
    ]
    packet = {"schema": "reviewed-extraction-input-v1", "documents": [
        {"selection_sha256": "synthetic", "packet_sha256": "synthetic",
         "blocks": [{"text": text, "source_spans": []} for text, _, _ in cases]}
    ]}
    result = run_model(packet, nlp)
    for (text, voice, flag), row in zip(cases, result["rows"], strict=True):
        events = [e for e in row["candidates"] if e["predicate_lemma"] == "build"]
        assert len(events) == 1, (text, row)
        event = events[0]
        assert event["voice"] == voice, (text, event)
        if flag:
            assert flag in event["review_flags"], (text, event)
        for field in ["actor", "object", "predicate", "sentence"]:
            s = event[field]
            assert text[s["start"]:s["end"]] == s["text"]
        assert event["delivery"] == "disabled" and event["mechanism"] == "UNKNOWN"
    assert result["rows"][1]["candidates"][0]["phase"] == "PROPOSED"
    print(json.dumps({"synthetic_model_cases_passed": len(cases), "human_gold": False}))


if __name__ == "__main__":
    main()
