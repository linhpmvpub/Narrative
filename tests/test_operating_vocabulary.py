import hashlib
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_company_profiles import dossier as dossier

from engine.company_profiles import ProfileBundle
from engine.operating_vocabulary import audit_vocabulary


@pytest.fixture
def vocabulary(dossier):
    root, data = dossier
    text = "Our example systems increased production this quarter."
    raw = ("<p>" + text + "</p>").encode()
    (root / "operations.html").write_bytes(raw)
    data["sources"].append({**data["sources"][0], "id": "ops", "file": "operations.html",
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "url": "https://www.sec.gov/Archives/edgar/data/123/000000012326000001/test.htm"})
    data["identifiers"] = {"CIK": "123"}
    data["factor_bindings"] = [{"id": "ops", "factor_id": "p",
        "kind": "ISSUER_OPERATING_CONTEXT", "topic_terms": ["example systems"],
        "context_terms": ["our example systems"], "change_terms": ["increased"],
        "issuer_supply_scope": True, "narrative_ids": ["n"], "scope": "Synthetic example",
        "reviewed_at": data["available_at"],
        "review_until": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "evidence": [{"source_id": "ops", "quote": text}]}]
    return root, data


def test_all_terms_have_exact_witnesses_without_writes(vocabulary):
    root, data = vocabulary
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    report = audit_vocabulary(root, ProfileBundle.model_validate(data), ["ops"])
    assert len(report["witnesses"]) == 3
    assert not report["production_activation"] and report["delivery"] == "disabled"
    text = data["factor_bindings"][0]["evidence"][0]["quote"]
    for witness in report["witnesses"]:
        assert all(text[s["start"]:s["end"]] == s["text"] for s in witness["spans"])
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


@pytest.mark.parametrize("group,term", [("topic_terms", "example"),
    ("context_terms", "our new systems"), ("change_terms", "demand")])
def test_each_added_term_needs_own_witness(vocabulary, group, term):
    root, data = vocabulary
    # Substring example is a valid literal; use an unsourced product for that group.
    data["factor_bindings"][0][group].append("other systems" if group == "topic_terms" else term)
    with pytest.raises(ValueError, match="source witness"):
        audit_vocabulary(root, ProfileBundle.model_validate(data), ["ops"])


@pytest.mark.parametrize("text", [
    "Our example systems are available. Production increased.",
    "Our example systems may see increased production.",
    "Our example systems did not see increased production.",
    "Our competitors increased production of example systems.",
    '"Our example systems increased production."',
])
def test_ambiguous_source_cannot_authorize_vocabulary(vocabulary, text):
    root, data = vocabulary
    raw = ("<p>" + text + "</p>").encode()
    (root / "operations.html").write_bytes(raw)
    data["sources"][-1]["sha256"] = hashlib.sha256(raw).hexdigest()
    data["factor_bindings"][0]["evidence"][0]["quote"] = text
    with pytest.raises(ValueError, match="source witness"):
        audit_vocabulary(root, ProfileBundle.model_validate(data), ["ops"])


def test_corrupt_source_and_unknown_selection_fail_closed(vocabulary):
    root, data = vocabulary
    bundle = ProfileBundle.model_validate(deepcopy(data))
    for selection in ([], ["missing"], ["ops", "ops"]):
        with pytest.raises(ValueError):
            audit_vocabulary(root, bundle, selection)
    (root / "operations.html").write_text("corruption")
    with pytest.raises(ValueError, match="Source version"):
        audit_vocabulary(root, bundle, ["ops"])


@pytest.mark.parametrize("url", [
    "https://www.sec.gov/Archives/edgar/data/456/000000012326000001/test.htm",
    "https://example.test/Archives/edgar/data/123/000000012326000001/test.htm",
    "https://www.sec.gov/Archives/edgar/data/123/000000012326000001/test.htm?other=1",
    "https://www.sec.gov/Archives/edgar/data/123/000000012326000001/../test.htm",
])
def test_other_issuer_or_untrusted_source_cannot_support_terms(vocabulary, url):
    root, data = vocabulary
    data["sources"][-1]["url"] = url
    with pytest.raises(ValueError, match="same-issuer SEC"):
        audit_vocabulary(root, ProfileBundle.model_validate(data), ["ops"])
