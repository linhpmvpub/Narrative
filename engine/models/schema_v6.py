"""Versioned source permissions and provenance for reviewed canonical ingestion."""

import sqlalchemy as sa

from engine.models.schema_v5 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)

permissions = sa.Table(
    "rie_sec_permissions",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("filing_id", sa.Text, sa.ForeignKey("rie_sec_filings.id"), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("operator_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
    sa.Column("capture_hash", sa.Text, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.UniqueConstraint("filing_id", "version"),
    sa.CheckConstraint("status IN ('approved','revoked')"),
)
promotions = sa.Table(
    "rie_sec_promotions",
    metadata,
    sa.Column("draft_id", sa.Text, sa.ForeignKey("rie_sec_drafts.id"), primary_key=True),
    sa.Column("review_id", sa.Text, sa.ForeignKey("rie_sec_reviews.id"), nullable=False),
    sa.Column("permission_id", sa.Text, sa.ForeignKey(permissions.c.id), nullable=False),
    sa.Column("operator_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column(
        "event_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        nullable=False,
    ),
    sa.Column(
        "document_id", sa.Uuid(as_uuid=False), sa.ForeignKey("rie_documents.id"), nullable=False
    ),
    sa.Column(
        "evidence_id", sa.Uuid(as_uuid=False), sa.ForeignKey("rie_evidence.id"), nullable=False
    ),
    sa.Column("input_hash", sa.Text, nullable=False),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("result", sa.JSON, nullable=False),
)
