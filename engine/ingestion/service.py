from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from engine.adapters.fixture import FixtureEvent
from engine.identity import validate_metric_issuer
from engine.ingestion.contracts import digest
from engine.models.contracts import utc
from engine.models.schema_v2 import database_mode, ingestion_receipts, metadata
from engine.seed import identifier


def initialize_demo(engine: Engine) -> None:
    """Explicitly mark a migrated, candidate-only database as synthetic forever."""
    with engine.begin() as conn:
        current = conn.execute(select(database_mode.c.mode)).scalar_one_or_none()
        if current == "synthetic":
            return
        if current is not None:
            raise ValueError("Cannot convert a production database to demo")
        for name in ("rie_documents", "rie_sources", "rie_evidence", "rie_events", "rie_alerts"):
            if conn.scalar(select(func.count()).select_from(metadata.tables[name])):
                raise ValueError("Demo initialization requires an empty source/event database")
        edges = metadata.tables["rie_relationships"]
        if conn.execute(select(edges.c.id).where(edges.c.status != "candidate")).first():
            raise ValueError("Demo initialization cannot adopt reviewed relationships")
        conn.execute(database_mode.insert().values(id=1, mode="synthetic"))


def _document(conn: Connection, item: FixtureEvent) -> tuple[str, str]:
    sources, docs, evidence = (
        metadata.tables[name] for name in ("rie_sources", "rie_documents", "rie_evidence")
    )
    if (
        conn.execute(select(sources.c.id).where(sources.c.id == "synthetic-fixtures")).first()
        is None
    ):
        conn.execute(
            sources.insert().values(
                id="synthetic-fixtures",
                name="SYNTHETIC offline fixture",
                origin="fixture",
                rights_status="blocked",
                citation_url="fixture://synthetic",
                rights_note="Approved only for isolated tests; never approved for live processing",
            )
        )
    doc_id = identifier("fixture-document:" + item.source_document_id)
    evidence_id = identifier("fixture-evidence:" + item.event_id)
    if conn.execute(select(docs.c.id).where(docs.c.id == doc_id)).first() is None:
        conn.execute(
            docs.insert().values(
                id=doc_id,
                source_id="synthetic-fixtures",
                external_id=item.source_document_id,
                primary_entity_id=item.primary_entity_id,
                source_url=item.source_url,
                title=item.headline_factual,
                content_sha256=digest(item.model_dump(mode="json")),
                published_at=item.published_at,
                first_seen_at=item.first_seen_at,
                available_at=item.available_at,
                retrieved_at=datetime.now(UTC),
                is_synthetic=True,
                metadata={
                    "fixture_payload": item.model_dump(mode="json"),
                    "source_url_sha256": digest(item.source_url),
                    "passage_basis": "synthetic fixture headline; no numeric evidence",
                },
            )
        )
        # Offsets are into the supplied fixture headline, never an invented market article.
        conn.execute(
            evidence.insert().values(
                id=evidence_id,
                document_id=doc_id,
                text_start=0,
                text_end=len(item.headline_factual),
                quoted_claim=item.headline_factual,
                url=item.source_url,
                created_at=datetime.now(UTC),
            )
        )
    return doc_id, evidence_id


def _review(conn: Connection, item: FixtureEvent, reason: str) -> None:
    table = metadata.tables["rie_review_queue"]
    key = identifier("ingestion-review:" + item.event_id + ":" + reason)
    if conn.execute(select(table.c.id).where(table.c.id == key)).first() is None:
        conn.execute(
            table.insert().values(id=key, item_kind="event", item_id=item.event_id, reason=reason)
        )


def _import(conn: Connection, item: FixtureEvent, as_of: datetime) -> dict:
    result = {
        "input_id": item.event_id,
        "canonical_event_key": item.canonical_event_key,
        "is_synthetic": True,
        "status": "ingested",
        "reason": "new_fact",
        "event_version_id": None,
    }

    def stop(status: str, reason: str) -> dict:
        result.update(status=status, reason=reason)
        if status in ("review_required", "rejected"):
            _review(conn, item, reason)
        return result

    if max(item.available_at, item.published_at, item.first_seen_at) > as_of:
        return stop("suppressed", "future_available_at")
    nodes = metadata.tables["rie_entities"]
    known = set(conn.execute(select(nodes.c.id)).scalars())
    if item.primary_entity_id not in known or item.driver_entity_id not in known:
        return stop("rejected", "unknown_entity")
    if item.event_type == "WDC_HDD_MIXUP":
        return stop("rejected", "issuer_identity_mismatch")
    try:
        validate_metric_issuer(
            item.primary_entity_id,
            item.driver_entity_id,
            (item.occurred_at or item.available_at).date(),
        )
    except ValueError:
        return stop("rejected", "issuer_identity_mismatch")
    doc_id, evidence_id = _document(conn, item)
    if item.event_type == "MISALIGNED_PERIOD":
        return stop("review_required", "incompatible_period")
    quality = item.fixture_metadata.q_test_input
    if quality is not None and quality < 0.70:
        return stop("suppressed", "low_evidence_quality")

    events, versions, links = (
        metadata.tables[name] for name in ("rie_events", "rie_event_versions", "rie_event_evidence")
    )
    event = (
        conn.execute(
            select(events)
            .where(events.c.canonical_event_key == item.canonical_event_key)
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    version_id = identifier("fixture-version:" + item.event_id)
    existing = conn.execute(
        select(versions.c.id).where(versions.c.id == version_id)
    ).scalar_one_or_none()
    if existing:
        result.update(status="duplicate", reason="already_ingested", event_version_id=existing)
        return result
    claim: dict = {
        "claim": item.claim.model_dump(mode="json"),
        "fixture_metadata": item.fixture_metadata.model_dump(mode="json"),
        "is_synthetic": True,
        "materiality": "UNKNOWN",
    }
    meta = item.fixture_metadata
    previous = None
    if event:
        if (
            event["issuer_entity_id"] != item.primary_entity_id
            or event["event_type"] != item.event_type
        ):
            return stop("review_required", "canonical_identity_conflict")
        previous = (
            conn.execute(
                select(versions)
                .where(versions.c.event_id == event["id"])
                .order_by(versions.c.version_number.desc())
            )
            .mappings()
            .first()
        )
    if meta.is_correction:
        if previous is None:
            return stop("review_required", "missing_correction_original")
        original_doc = conn.execute(
            select(metadata.tables["rie_documents"].c.metadata).where(
                metadata.tables["rie_documents"].c.id == previous["document_id"]
            )
        ).scalar_one()
        if meta.supersedes != original_doc["fixture_payload"]["event_id"]:
            return stop("review_required", "correction_target_not_latest")
        if item.available_at <= utc(previous["available_at"]):
            return stop("review_required", "non_monotonic_correction")
        # These fixtures contain no revised numeric values. Preserve the explicitly
        # declared synthetic correction; do not infer magnitude or market materiality.
        if (
            claim["claim"] == previous["normalized_claim"]["claim"]
            and item.headline_factual == previous["factual_headline"]
        ):
            return stop("review_required", "correction_without_changed_claim")
    elif previous:
        # Ordinary coverage must not overwrite a fact or create a new version.
        original_doc = conn.execute(
            select(metadata.tables["rie_documents"].c.metadata).where(
                metadata.tables["rie_documents"].c.id == previous["document_id"]
            )
        ).scalar_one()
        if meta.reprint_of and meta.reprint_of != original_doc["fixture_payload"]["event_id"]:
            # Reprints of an older version remain attached to that older version.
            if event is None:
                raise ValueError("Version without canonical event")
            old = (
                conn.execute(select(versions).where(versions.c.event_id == event["id"]))
                .mappings()
                .all()
            )
            previous = next(
                (
                    v
                    for v in old
                    if v["normalized_claim"]["fixture_metadata"].get("input_id") == meta.reprint_of
                ),
                None,
            )
            if previous is None:
                return stop("review_required", "unknown_reprint_target")
        if claim["claim"] != previous["normalized_claim"]["claim"]:
            return stop("review_required", "conflicting_fact_requires_correction")
        result.update(
            status="duplicate", reason="canonical_reprint", event_version_id=previous["id"]
        )
        if (
            conn.execute(
                select(links).where(
                    links.c.event_version_id == previous["id"], links.c.evidence_id == evidence_id
                )
            ).first()
            is None
        ):
            conn.execute(
                links.insert().values(event_version_id=previous["id"], evidence_id=evidence_id)
            )
        return result
    elif meta.reprint_of:
        return stop("review_required", "missing_reprint_original")

    if event is None:
        conn.execute(
            events.insert().values(
                id=item.event_id,
                canonical_event_key=item.canonical_event_key,
                issuer_entity_id=item.primary_entity_id,
                event_type=item.event_type,
                occurred_at=item.occurred_at,
                published_at=item.published_at,
                first_seen_at=item.first_seen_at,
                available_at=item.available_at,
                is_synthetic=True,
            )
        )
    event_id = event["id"] if event else item.event_id
    claim["fixture_metadata"]["input_id"] = item.event_id
    conn.execute(
        versions.insert().values(
            id=version_id,
            event_id=event_id,
            version_number=previous["version_number"] + 1 if previous else 1,
            factual_headline=item.headline_factual,
            normalized_claim=claim,
            metric_id=item.driver_entity_id,
            extraction_model="fixture-none-v1",
            document_id=doc_id,
            evidence_quality=quality,
            available_at=item.available_at,
            is_correction=meta.is_correction,
            supersedes_version_id=previous["id"] if meta.is_correction and previous else None,
        )
    )
    conn.execute(links.insert().values(event_version_id=version_id, evidence_id=evidence_id))
    result["event_version_id"] = version_id
    if meta.is_correction:
        result.update(status="versioned_correction", reason="explicit_synthetic_correction")
    return result


def ingest_fixtures(engine: Engine, records: list[FixtureEvent], as_of: datetime) -> list[dict]:
    if as_of.tzinfo is None:
        raise ValueError("as_of requires timezone")
    as_of = as_of.astimezone(UTC)
    results = []
    # One writer per database: serializes dedup/version checks on PostgreSQL.
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        mode = conn.execute(
            select(database_mode.c.mode).where(database_mode.c.id == 1).with_for_update()
        ).scalar_one_or_none()
        if mode != "synthetic":
            raise ValueError("Fixture ingestion requires explicitly initialized synthetic database")
        for item in sorted(
            records,
            key=lambda x: (
                x.available_at,
                bool(x.fixture_metadata.reprint_of or x.fixture_metadata.is_correction),
                x.event_id,
            ),
        ):
            input_hash = digest(item.model_dump(mode="json"))
            hashes = set(
                conn.execute(
                    select(ingestion_receipts.c.input_sha256).where(
                        ingestion_receipts.c.input_id == item.event_id
                    )
                ).scalars()
            )
            if hashes and hashes != {input_hash}:
                raise ValueError(
                    "Input ID reused with changed content; use an explicit new correction ID"
                )
            receipt_id = digest([item.event_id, as_of.isoformat()])
            prior = (
                conn.execute(
                    select(ingestion_receipts).where(ingestion_receipts.c.id == receipt_id)
                )
                .mappings()
                .one_or_none()
            )
            if prior:
                results.append(
                    {
                        "input_id": item.event_id,
                        "canonical_event_key": item.canonical_event_key,
                        "is_synthetic": True,
                        "status": prior["status"],
                        "reason": prior["reason"],
                        "event_version_id": prior["event_version_id"],
                        "idempotent_retry": True,
                    }
                )
                continue
            result = _import(conn, item, as_of)
            conn.execute(
                ingestion_receipts.insert().values(
                    id=receipt_id,
                    input_id=item.event_id,
                    input_sha256=input_hash,
                    as_of=as_of,
                    status=result["status"],
                    reason=result["reason"],
                    event_version_id=result["event_version_id"],
                )
            )
            results.append(result)
    return results


def versions_as_of(conn: Connection, as_of: datetime) -> list[dict]:
    """Synthetic snapshot helper; never replay a live database with fixture clocks."""
    if as_of.tzinfo is None:
        raise ValueError("as_of requires timezone")
    if (
        conn.execute(
            select(database_mode.c.mode).where(database_mode.c.id == 1)
        ).scalar_one_or_none()
        != "synthetic"
    ):
        raise ValueError("Fixture replay requires a synthetic database")
    versions, docs = metadata.tables["rie_event_versions"], metadata.tables["rie_documents"]
    rows = conn.execute(
        select(versions)
        .join(docs, versions.c.document_id == docs.c.id)
        .where(
            versions.c.available_at <= as_of,
            docs.c.available_at <= as_of,
            docs.c.published_at <= as_of,
            docs.c.first_seen_at <= as_of,
        )
        .order_by(versions.c.event_id, versions.c.version_number)
    ).mappings()
    latest = {row["event_id"]: dict(row) for row in rows}
    return sorted(latest.values(), key=lambda row: (row["available_at"], row["event_id"]))
