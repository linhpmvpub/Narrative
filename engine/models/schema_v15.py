"""Canonical news ingestion audit receipts."""

import sqlalchemy as sa

from engine.models.schema_v14 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)
news_promotions = sa.Table(
    "rie_news_promotions",
    metadata,
    sa.Column("claim_id", sa.Text, sa.ForeignKey("rie_news_claims.id"), primary_key=True),
    sa.Column("review_id", sa.Text, sa.ForeignKey("rie_news_claim_reviews.id"), nullable=False),
    sa.Column("operator_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column(
        "event_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        nullable=False,
    ),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("input_sha256", sa.Text, nullable=False),
    sa.Column("request", sa.JSON, nullable=False),
    sa.Column("result", sa.JSON, nullable=False),
)
