"""Audit curated operating vocabulary against exact profile evidence, without activation."""

import re
from urllib.parse import urlsplit

from engine.company_profiles import verify_sources
from engine.ingestion.contracts import digest
from engine.issuer_operations import operating_matches
from engine.supply_roles import valid_cik


def audit_vocabulary(directory, bundle, binding_ids):
    """Every proposed literal needs a same-sentence own-issuer evidence witness.

    This is a lexical/provenance gate, not independent approval of narrative semantics.
    Caller must retain source limitations and obtain separate validation before activation.
    """
    if not binding_ids or len(set(binding_ids)) != len(binding_ids):
        raise ValueError("Select unique explicit bindings")
    verify_sources(directory, bundle)
    cik = bundle.identifiers.get("CIK")
    if not valid_cik(cik):
        raise ValueError("Trusted profile issuer required")
    bindings = {b.id: b for b in bundle.factor_bindings}
    if not set(binding_ids) <= bindings.keys():
        raise ValueError("Unknown vocabulary binding")
    sources = {s.id: s for s in bundle.sources}
    witnesses = []
    for key in binding_ids:
        binding = bindings[key]
        if binding.kind != "ISSUER_OPERATING_CONTEXT":
            raise ValueError("Only explicit operating bindings supported")
        for evidence in binding.evidence:
            url = urlsplit(str(sources[evidence.source_id].url))
            path = re.fullmatch(r"/Archives/edgar/data/([0-9]+)/[0-9]{18}/[A-Za-z0-9_.-]+\.html?", url.path)
            if (url.scheme != "https" or url.netloc != "www.sec.gov" or url.query or url.fragment
                    or path is None or int(path[1]) != int(cik)):
                raise ValueError("Operating vocabulary requires same-issuer SEC source")
        for group in ("topic_terms", "context_terms", "change_terms"):
            for term in getattr(binding, group):
                probe = binding.model_copy(update={group: [term]})
                witness = None
                for evidence in binding.evidence:
                    spans = operating_matches(probe, evidence.quote, cik, cik)
                    if spans:
                        witness = {"binding_id": key, "group": group, "term": term,
                            "source_id": evidence.source_id, "quote_sha256": digest(evidence.quote),
                            "spans": spans}
                        break
                if witness is None:
                    raise ValueError(f"No same-sentence source witness for {key}:{group}:{term}")
                witnesses.append(witness)
    return {"profile_id": bundle.id, "profile_version": bundle.version,
            "profile_sha256": digest(bundle.model_dump(mode="json")),
            "witnesses": witnesses, "validation_kind": "LEXICAL_SOURCE_AUDIT_NOT_SEMANTIC_APPROVAL",
            "production_activation": False, "delivery": "disabled"}
