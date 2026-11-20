"""Frozen v0001 schema, translated from the supplied reference DDL."""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()

rie_entities = sa.Table(
    "rie_entities",
    metadata,
    sa.Column("id", sa.TEXT(), primary_key=True, nullable=False),
    sa.Column("entity_type", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("display_name", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "metadata",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.CheckConstraint(
        "entity_type IN ('company','product_market','driver','financial_metric','policy_or_constraint')"
    ),
)

rie_replay_runs = sa.Table(
    "rie_replay_runs",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column("as_of", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column("dataset_version", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("policy_version", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("model_version", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "metrics",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column(
        "started_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("finished_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column(
        "status", sa.TEXT(), primary_key=False, nullable=False, server_default=sa.text("'started'")
    ),
    sa.Column(
        "artifacts",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
)

rie_review_queue = sa.Table(
    "rie_review_queue",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column("item_kind", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("item_id", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "priority", sa.INTEGER(), primary_key=False, nullable=False, server_default=sa.text("3")
    ),
    sa.Column("reason", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "status", sa.TEXT(), primary_key=False, nullable=False, server_default=sa.text("'open'")
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("resolved_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.CheckConstraint("status IN ('open','resolved','rejected')"),
    sa.CheckConstraint("item_kind IN ('relation','event','source','claim','policy')"),
)

rie_sources = sa.Table(
    "rie_sources",
    metadata,
    sa.Column("id", sa.TEXT(), primary_key=True, nullable=False),
    sa.Column("name", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("origin", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("rights_status", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("citation_url", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("rights_note", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.CheckConstraint("rights_status IN ('approved','pending','blocked')"),
)

rie_documents = sa.Table(
    "rie_documents",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "source_id", sa.TEXT(), sa.ForeignKey("rie_sources.id"), primary_key=False, nullable=False
    ),
    sa.Column("external_id", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "primary_entity_id",
        sa.TEXT(),
        sa.ForeignKey("rie_entities.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column("filing_form", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column("source_url", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("title", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column("content_sha256", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column("available_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column(
        "retrieved_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column(
        "is_synthetic",
        sa.BOOLEAN(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "metadata",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.UniqueConstraint("source_id", "source_url", "content_sha256"),
)
sa.Index("ix_rie_docs_available", rie_documents.c.available_at, unique=False)

rie_entity_aliases = sa.Table(
    "rie_entity_aliases",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "entity_id", sa.TEXT(), sa.ForeignKey("rie_entities.id"), primary_key=False, nullable=False
    ),
    sa.Column("symbol", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("exchange", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "alias_kind",
        sa.TEXT(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'ticker'"),
    ),
    sa.Column("effective_from", sa.DATE(), primary_key=False, nullable=True),
    sa.Column("effective_until", sa.DATE(), primary_key=False, nullable=True),
    sa.Column("external_id", sa.TEXT(), primary_key=False, nullable=True),
    sa.UniqueConstraint("entity_id", "symbol", "alias_kind", "effective_from"),
)
sa.Index("ix_rie_alias_symbol", rie_entity_aliases.c.symbol, unique=False)

rie_events = sa.Table(
    "rie_events",
    metadata,
    sa.Column("id", sa.TEXT(), primary_key=True, nullable=False),
    sa.Column("canonical_event_key", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "issuer_entity_id",
        sa.TEXT(),
        sa.ForeignKey("rie_entities.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column("event_type", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column("available_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column(
        "is_synthetic",
        sa.BOOLEAN(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.UniqueConstraint("canonical_event_key"),
)
sa.Index("ix_rie_events_available", rie_events.c.available_at, unique=False)

rie_narratives = sa.Table(
    "rie_narratives",
    metadata,
    sa.Column("id", sa.TEXT(), primary_key=True, nullable=False),
    sa.Column(
        "ticker_entity_id",
        sa.TEXT(),
        sa.ForeignKey("rie_entities.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("owner_user_id", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "is_template",
        sa.BOOLEAN(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column("status", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.CheckConstraint("status IN ('template_draft','draft','active','paused','archived')"),
    sa.CheckConstraint("is_template OR owner_user_id IS NOT NULL"),
)

rie_relationships = sa.Table(
    "rie_relationships",
    metadata,
    sa.Column("id", sa.TEXT(), primary_key=True, nullable=False),
    sa.Column(
        "from_entity_id",
        sa.TEXT(),
        sa.ForeignKey("rie_entities.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "to_entity_id",
        sa.TEXT(),
        sa.ForeignKey("rie_entities.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("relation_family", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("mechanism", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("sign", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("lag", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("strength", sa.NUMERIC(precision=5, scale=4), primary_key=False, nullable=True),
    sa.Column(
        "confidence",
        sa.NUMERIC(precision=5, scale=4),
        primary_key=False,
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.Column(
        "status",
        sa.TEXT(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'candidate'"),
    ),
    sa.Column("valid_from", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column("valid_until", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column(
        "recorded_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("verified_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column("verified_by", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "metadata",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.CheckConstraint("sign IN ('positive','negative','conditional','unknown')"),
    sa.CheckConstraint("status IN ('candidate','verified','rejected','stale')"),
    sa.CheckConstraint(
        "relation_family IN ('CUSTOMER_DEMAND','SUPPLIER_COST','COMPETITOR_SUPPLY','PRODUCT_MARKET','MACRO_POLICY','FINANCIAL_TRANSMISSION')"
    ),
    sa.CheckConstraint("confidence BETWEEN 0 AND 1"),
    sa.CheckConstraint("strength BETWEEN 0 AND 1"),
    sa.CheckConstraint("from_entity_id <> to_entity_id"),
    sa.CheckConstraint("lag IN ('immediate','short','long','variable')"),
    sa.CheckConstraint(
        "status <> 'verified' OR (verified_at IS NOT NULL AND verified_by IS NOT NULL)"
    ),
)
sa.Index(
    "ix_rie_edges_from",
    rie_relationships.c.from_entity_id,
    rie_relationships.c.status,
    unique=False,
)
sa.Index(
    "ix_rie_edges_to", rie_relationships.c.to_entity_id, rie_relationships.c.status, unique=False
)

rie_event_versions = sa.Table(
    "rie_event_versions",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "event_id", sa.TEXT(), sa.ForeignKey("rie_events.id"), primary_key=False, nullable=False
    ),
    sa.Column("version_number", sa.INTEGER(), primary_key=False, nullable=False),
    sa.Column("factual_headline", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "normalized_claim",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "metric_id", sa.TEXT(), sa.ForeignKey("rie_entities.id"), primary_key=False, nullable=True
    ),
    sa.Column("extraction_model", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "document_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_documents.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column(
        "evidence_quality", sa.NUMERIC(precision=5, scale=4), primary_key=False, nullable=True
    ),
    sa.Column("available_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column(
        "is_correction",
        sa.BOOLEAN(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "supersedes_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.UniqueConstraint("event_id", "version_number"),
    sa.CheckConstraint("evidence_quality BETWEEN 0 AND 1"),
)

rie_evidence = sa.Table(
    "rie_evidence",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "document_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_documents.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("text_start", sa.INTEGER(), primary_key=False, nullable=True),
    sa.Column("text_end", sa.INTEGER(), primary_key=False, nullable=True),
    sa.Column("excerpt", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column("quoted_claim", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("url", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("verified_by", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column("verified_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
)

rie_narrative_versions = sa.Table(
    "rie_narrative_versions",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "narrative_id",
        sa.TEXT(),
        sa.ForeignKey("rie_narratives.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("version_number", sa.INTEGER(), primary_key=False, nullable=False),
    sa.Column("title", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("thesis", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("horizon_months", sa.INTEGER(), primary_key=False, nullable=False),
    sa.Column(
        "config", sa.JSON().with_variant(JSONB(), "postgresql"), primary_key=False, nullable=False
    ),
    sa.Column(
        "published_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column(
        "available_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("approved_by", sa.TEXT(), primary_key=False, nullable=True),
    sa.UniqueConstraint("narrative_id", "version_number"),
    sa.CheckConstraint("horizon_months BETWEEN 1 AND 60"),
)

rie_relationship_revisions = sa.Table(
    "rie_relationship_revisions",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "relationship_id",
        sa.TEXT(),
        sa.ForeignKey("rie_relationships.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "before", sa.JSON().with_variant(JSONB(), "postgresql"), primary_key=False, nullable=True
    ),
    sa.Column(
        "after", sa.JSON().with_variant(JSONB(), "postgresql"), primary_key=False, nullable=False
    ),
    sa.Column("reviewer_id", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column("reason", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "changed_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
)

rie_subscriptions = sa.Table(
    "rie_subscriptions",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column("user_id", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("thread_kind", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "stock_entity_id",
        sa.TEXT(),
        sa.ForeignKey("rie_entities.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column(
        "narrative_id",
        sa.TEXT(),
        sa.ForeignKey("rie_narratives.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.Column("disabled_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column(
        "preferences",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.CheckConstraint(
        "(thread_kind='stock' AND stock_entity_id IS NOT NULL AND narrative_id IS NULL) OR\n        (thread_kind='narrative' AND narrative_id IS NOT NULL AND stock_entity_id IS NULL)"
    ),
    sa.CheckConstraint("thread_kind IN ('stock','narrative')"),
)
sa.Index(
    "ux_rie_active_stock_sub",
    rie_subscriptions.c.user_id,
    rie_subscriptions.c.stock_entity_id,
    unique=True,
    sqlite_where=sa.text("disabled_at IS NULL AND thread_kind='stock'"),
    postgresql_where=sa.text("disabled_at IS NULL AND thread_kind='stock'"),
)
sa.Index(
    "ux_rie_active_nav_sub",
    rie_subscriptions.c.user_id,
    rie_subscriptions.c.narrative_id,
    unique=True,
    sqlite_where=sa.text("disabled_at IS NULL AND thread_kind='narrative'"),
    postgresql_where=sa.text("disabled_at IS NULL AND thread_kind='narrative'"),
)

rie_event_evidence = sa.Table(
    "rie_event_evidence",
    metadata,
    sa.Column(
        "event_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "evidence_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_evidence.id"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
)

rie_match_decisions = sa.Table(
    "rie_match_decisions",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "event_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "narrative_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_narrative_versions.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("as_of", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column(
        "chosen_path",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'[]'"),
    ),
    sa.Column(
        "gate_results",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column(
        "score_components",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column("score", sa.NUMERIC(precision=6, scale=3), primary_key=False, nullable=True),
    sa.Column("materiality_status", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("stance", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("decision", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "explanation",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.Column("policy_version", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("model_version", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.CheckConstraint(
        "stance IN ('SUPPORTS','CHALLENGES','MIXED','NO_CHANGE','INSUFFICIENT_EVIDENCE')"
    ),
    sa.CheckConstraint("score BETWEEN 0 AND 100"),
    sa.CheckConstraint("decision IN ('push','digest','storybook','suppressed','review_required')"),
    sa.UniqueConstraint("event_version_id", "narrative_version_id", "as_of", "policy_version"),
    sa.CheckConstraint("materiality_status IN ('KNOWN','UNKNOWN','REVIEW_REQUIRED')"),
)
sa.Index(
    "ix_rie_decision_nav",
    rie_match_decisions.c.narrative_version_id,
    rie_match_decisions.c.as_of,
    unique=False,
)

rie_metric_observations = sa.Table(
    "rie_metric_observations",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "entity_id", sa.TEXT(), sa.ForeignKey("rie_entities.id"), primary_key=False, nullable=False
    ),
    sa.Column("metric_id", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("period_start", sa.DATE(), primary_key=False, nullable=True),
    sa.Column("period_end", sa.DATE(), primary_key=False, nullable=False),
    sa.Column("value", sa.NUMERIC(), primary_key=False, nullable=False),
    sa.Column("unit", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("accounting_basis", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column("first_available_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column(
        "evidence_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_evidence.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column(
        "adjustment_metadata",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
)
sa.Index(
    "ix_rie_metrics_asof",
    rie_metric_observations.c.entity_id,
    rie_metric_observations.c.metric_id,
    rie_metric_observations.c.first_available_at,
    unique=False,
)

rie_narrative_drivers = sa.Table(
    "rie_narrative_drivers",
    metadata,
    sa.Column(
        "narrative_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_narrative_versions.id"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "driver_entity_id",
        sa.TEXT(),
        sa.ForeignKey("rie_entities.id"),
        primary_key=True,
        nullable=False,
    ),
    sa.Column("priority", sa.SMALLINT(), primary_key=False, nullable=False),
    sa.Column(
        "config",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'{}'"),
    ),
    sa.CheckConstraint("priority BETWEEN 1 AND 5"),
)

rie_relationship_evidence = sa.Table(
    "rie_relationship_evidence",
    metadata,
    sa.Column(
        "relationship_id",
        sa.TEXT(),
        sa.ForeignKey("rie_relationships.id"),
        primary_key=True,
        nullable=False,
    ),
    sa.Column(
        "evidence_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_evidence.id"),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
)

rie_alerts = sa.Table(
    "rie_alerts",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column("user_id", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("canonical_event_key", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "event_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "primary_decision_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_match_decisions.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "related_thread_ids",
        sa.JSON().with_variant(JSONB(), "postgresql"),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'[]'"),
    ),
    sa.Column("dispatch_kind", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "delivery_status",
        sa.TEXT(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("'dry_run'"),
    ),
    sa.Column("sent_at", sa.DateTime(timezone=True), primary_key=False, nullable=True),
    sa.Column("provider_message_id", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.CheckConstraint("dispatch_kind IN ('push','digest','storybook')"),
    sa.UniqueConstraint("user_id", "canonical_event_key", "dispatch_kind", "event_version_id"),
    sa.CheckConstraint("delivery_status IN ('dry_run','queued','sent','failed','cancelled')"),
)

rie_story_entries = sa.Table(
    "rie_story_entries",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "narrative_id",
        sa.TEXT(),
        sa.ForeignKey("rie_narratives.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "narrative_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_narrative_versions.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "event_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column(
        "decision_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_match_decisions.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("available_at", sa.DateTime(timezone=True), primary_key=False, nullable=False),
    sa.Column("state_delta", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column(
        "correction_of",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_story_entries.id"),
        primary_key=False,
        nullable=True,
    ),
    sa.Column(
        "is_public",
        sa.BOOLEAN(),
        primary_key=False,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.UniqueConstraint("narrative_version_id", "event_version_id"),
)

rie_feedback = sa.Table(
    "rie_feedback",
    metadata,
    sa.Column(
        "id",
        sa.Uuid(as_uuid=False),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    ),
    sa.Column(
        "alert_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_alerts.id"),
        primary_key=False,
        nullable=False,
    ),
    sa.Column("user_id", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("label", sa.TEXT(), primary_key=False, nullable=False),
    sa.Column("reason_code", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column("free_text", sa.TEXT(), primary_key=False, nullable=True),
    sa.Column(
        "active", sa.BOOLEAN(), primary_key=False, nullable=False, server_default=sa.text("true")
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        primary_key=False,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    ),
    sa.CheckConstraint("label IN ('USEFUL','ALREADY_KNEW','NOT_RELEVANT','UNCLEAR','WRONG')"),
)
sa.Index(
    "ux_rie_feedback_active",
    rie_feedback.c.user_id,
    rie_feedback.c.alert_id,
    unique=True,
    sqlite_where=sa.text("active=true"),
    postgresql_where=sa.text("active=true"),
)
