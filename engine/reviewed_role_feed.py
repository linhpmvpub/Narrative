"""Read-only shared SEC role cards. Revalidate current primary provenance on every read."""

from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.exc import NoResultFound

from engine.company_profiles import available_bundles
from engine.ingestion.contracts import digest
from engine.ingestion.reviewed import (
    documents,
    events,
    evidence,
    fact,
    links,
    permission_at,
    sources,
    validate_reviewed,
    versions,
)
from engine.models.contracts import utc
from engine.models.schema_v5 import drafts, filings
from engine.models.schema_v6 import promotions
from engine.profile_routing import binding_decisions
from engine.sec_review import require_real
from engine.settings import Settings
from engine.supply_roles import extract_supply_roles


def primary_source(conn, version, at):
    draft = conn.execute(select(drafts).where(
        drafts.c.id == version["normalized_claim"].get("draft_id"))).mappings().first()
    if not draft:
        raise ValueError("Primary draft absent")
    filing = conn.execute(select(filings).where(filings.c.id == draft["filing_id"])).mappings().one()
    notice_id = "development_sec_notice:" + filing["ticker"] + ":" + filing["accession"]
    lifecycle = conn.execute(select(versions).where(versions.c.event_id == notice_id)
                             .order_by(versions.c.version_number.desc()).limit(1)).mappings().first()
    if lifecycle and (utc(lifecycle["available_at"]) > at
                      or lifecycle["normalized_claim"].get("source_status", "active") != "active"):
        raise ValueError("Latest filing lifecycle is not active")
    event, review = validate_reviewed(conn, draft, filing, at)
    canonical = conn.execute(select(events).where(events.c.id == version["event_id"])).mappings().one()
    permission = permission_at(conn, filing, at)
    receipt = conn.execute(select(promotions).where(promotions.c.draft_id == draft["id"])).mappings().first()
    if (not receipt or utc(receipt["recorded_at"]) > at
            or receipt["event_version_id"] != version["id"]
            or receipt["review_id"] != review["id"]
            or receipt["input_hash"] != digest([draft["payload"], review["id"],
                                               filing["content_sha256"], filing["text_sha256"]])
            or version["normalized_claim"].get("extraction") != event.model_dump(mode="json")
            or version["normalized_claim"].get("fact") != fact(event)
            or version["event_id"] != draft["canonical_key"]
            or canonical["issuer_entity_id"] != event.entity_ids[0]
            or canonical["canonical_event_key"] != draft["canonical_key"]
            or version["normalized_claim"].get("review_id") != review["id"]
            or version["normalized_claim"].get("permission_id") != receipt["permission_id"]
            or version["normalized_claim"].get("is_synthetic") is not False
            or utc(version["available_at"]) != utc(receipt["recorded_at"])):
        raise ValueError("Canonical provenance changed")
    doc = conn.execute(select(documents).where(documents.c.id == version["document_id"])).mappings().one()
    source = conn.execute(select(sources).where(sources.c.id == doc["source_id"])).mappings().one()
    proof = conn.execute(select(evidence).where(evidence.c.id == receipt["evidence_id"])).mappings().one()
    claim = event.claims[0]
    linked = conn.execute(select(links).where(links.c.event_version_id == version["id"],
                                             links.c.evidence_id == proof["id"])).first()
    if (not linked or doc["id"] != receipt["document_id"] or doc["is_synthetic"]
            or doc["content_sha256"] != filing["content_sha256"]
            or doc["metadata"].get("text_sha256") != filing["text_sha256"]
            or doc["source_url"] != filing["source_url"]
            or doc["primary_entity_id"] != event.entity_ids[0]
            or source["id"] != "sec-reviewed:" + filing["id"]
            or source["rights_status"] != "approved"
            or source["citation_url"] != filing["source_url"]
            or utc(doc["retrieved_at"]) != utc(filing["retrieved_at"])
            or utc(proof["created_at"]) > at
            or proof["document_id"] != doc["id"] or proof["url"] != filing["source_url"]
            or proof["excerpt"] != claim.claim_text or proof["quoted_claim"] != claim.claim_text
            or proof["text_start"] != claim.source_span.start or proof["text_end"] != claim.source_span.end
            or proof["verified_by"] != review["reviewer_id"]
            or utc(proof["verified_at"]) != utc(review["reviewed_at"])):
        raise ValueError("Document/evidence provenance changed")
    return event, filing, claim, review, permission


def role_feed(conn, limit=100, *, operating=False):
    at = datetime.now(UTC)
    result: dict = {"items": [], "enabled": Settings.from_env().dev_informational_feed,
              "delivery": "disabled", "graph_modified": False, "as_of": at.isoformat(),
              "examined": 0, "withheld": 0, "truncated": False,
              "mode": ("REVIEWED_SEC_OPERATING_CONTEXT_NOT_VERIFIED_IMPACT" if operating
                       else "REVIEWED_SEC_ROLE_CONTEXT_NOT_VERIFIED_IMPACT")}
    if not result["enabled"]:
        return result
    if not 1 <= limit <= 200:
        raise ValueError("Bounded read required")
    require_real(conn)
    profiles = available_bundles(at)
    if profiles.get("withheld") or profiles.get("truncated") or not profiles["enabled"]:
        return {**result, "withheld": profiles.get("withheld", 0), "profiles_unavailable": True}
    newer = versions.alias("newer_role_version")
    query = select(versions).join(events, events.c.id == versions.c.event_id).where(
        events.c.is_synthetic.is_(False), versions.c.available_at <= at,
        ~exists(select(newer.c.id).where(newer.c.event_id == versions.c.event_id,
                                        newer.c.version_number > versions.c.version_number)),
        versions.c.normalized_claim["draft_id"].as_string().is_not(None),
    ).order_by(versions.c.available_at.desc(), versions.c.id).limit(limit + 1)
    rows = conn.execute(query).mappings().all()
    result["truncated"] = len(rows) > limit
    cards = []
    for version in rows[:limit]:
        result["examined"] += 1
        try:
            event, filing, claim, review, permission = primary_source(conn, version, at)
        except (ValueError, KeyError, TypeError, NoResultFound):
            result["withheld"] += 1
            continue
        role_data = extract_supply_roles(claim.claim_text, filing["manifest"]["cik"])
        if role_data["routing_withheld"] or (not operating and not role_data["facts"]):
            continue
        for b in profiles["items"]:
            for n in b.narratives:
                decisions = list(binding_decisions(b, n, {"summary": claim.claim_text}, at,
                                                  issuer_cik=filing["manifest"]["cik"]))
                decisions = [d for d in decisions if
                    (d["binding"].kind == "ISSUER_OPERATING_CONTEXT") == operating]
                if not decisions:
                    continue
                nodes = {node.id: node.label for node in b.nodes}
                cards.append({"id": digest((version["id"], b.id, n.id, "operating") if operating
                                         else (version["id"], b.id, n.id)),
                    "context_kind": "ISSUER_OPERATING_CONTEXT" if operating else "SUPPLY_ROLE",
                    "event_id": version["event_id"], "event_version_id": version["id"],
                    "version": version["version_number"], "headline": event.factual_headline,
                    "excerpt": claim.claim_text, "source_url": filing["source_url"],
                    "source_span": claim.source_span.model_dump(),
                    "source_sha256": filing["content_sha256"], "text_sha256": filing["text_sha256"],
                    "issuer": filing["ticker"], "issuer_cik": filing["manifest"]["cik"],
                    "published_at": event.published_at.isoformat(),
                    "source_time_basis": "SEC_FILING_DATE",
                    "available_at": max(utc(version["available_at"]), b.available_at).isoformat(),
                    "reviewed_at": utc(review["reviewed_at"]).isoformat(),
                    "reviewer_kind": review["payload"].get("reviewer_kind", "UNSPECIFIED"),
                    "source_permission_until": utc(permission["valid_until"]).isoformat(),
                    "ticker": b.ticker, "profile_id": b.id, "profile_version": b.version,
                    "profile_sources": [{"id": s.id, "url": str(s.url)} for s in b.sources],
                    "narrative_id": n.id, "narrative_title": n.title,
                    "roles": [{**r, "document_start": claim.source_span.start + r["start"],
                               "document_end": claim.source_span.start + r["end"]} for r in ([] if operating else role_data["facts"])],
                    "links": [{"binding_id": d["binding"].id, "kind": d["binding"].kind,
                        "scope": d["binding"].scope, "matches": d["matches"],
                        "path": [{"from": nodes[r.from_id], "to": nodes[r.to_id],
                                  "scope": r.scope, "evidence": [e.model_dump() for e in r.evidence]}
                                 for r in d["path"]]} for d in decisions],
                    "stance": "RELATED_INFORMATION", "impact": "UNKNOWN", "delivery": "disabled",
                    "impact_eligible": False, "graph_eligible": False,
                    "current_relationship_verified": False, "identity_merged": False,
                    "verification": ("REVIEWED_ISSUER_OPERATING_CONTEXT_NOT_VERIFIED_IMPACT" if operating
                                     else "REVIEWED_SOURCE_ROLE_CONTEXT_NOT_VERIFIED_RELATIONSHIP"),
                    "decision_trace": ["Chỉ dùng phiên bản sự kiện mới nhất; không dùng lại bản đã bị thay thế",
                        "Đã kiểm tra lại phê duyệt độc lập, quyền nguồn, danh tính và đoạn trích",
                        ("Cùng doanh nghiệp phát hành; cụm từ hoạt động và sản phẩm nằm trong một câu" if operating
                         else "Vai trò mua–cung cấp và sản phẩm giữ nguyên vị trí trong nguồn"),
                        "Chỉ ghép vào narrative khi hồ sơ và đường liên quan còn đủ bằng chứng",
                        "Chưa xác nhận quan hệ hiện tại hoặc quy mô tài chính; không gửi thông báo"]})
    result["items"] = cards[:100]
    result["truncated"] |= len(cards) > 100
    return result
