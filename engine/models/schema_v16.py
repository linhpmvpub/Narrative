"""Immutable exposure drafts and independently reviewed decisions."""

import sqlalchemy as sa

from engine.models.schema_v15 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)
exposure_drafts = sa.Table(
    "rie_news_exposure_drafts",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("claim_id", sa.Text, sa.ForeignKey("rie_news_claims.id"), nullable=False),
    sa.Column("author_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("input_sha256", sa.Text, nullable=False),
)
exposure_reviews = sa.Table(
    "rie_news_exposure_reviews",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("draft_id", sa.Text, sa.ForeignKey("rie_news_exposure_drafts.id"), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("reviewer_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("decision", sa.Text, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.UniqueConstraint("draft_id", "version"),
    sa.CheckConstraint("decision IN ('approved','rejected','revoked')"),
)
