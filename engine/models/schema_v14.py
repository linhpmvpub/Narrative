"""Immutable news claims, independent-account reviews and intake receipts."""

import sqlalchemy as sa

from engine.models.schema_v13 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)

news_claims = sa.Table(
    "rie_news_claims",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("revision_id", sa.Text, sa.ForeignKey("rie_news_revisions.id"), nullable=False),
    sa.Column("author_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("input_sha256", sa.Text, nullable=False),
)
news_claim_reviews = sa.Table(
    "rie_news_claim_reviews",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("claim_id", sa.Text, sa.ForeignKey("rie_news_claims.id"), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("reviewer_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("decision", sa.Text, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.UniqueConstraint("claim_id", "version"),
    sa.CheckConstraint("decision IN ('approved','rejected','revoked')"),
)
news_claim_intakes = sa.Table(
    "rie_news_claim_intakes",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("claim_id", sa.Text, sa.ForeignKey("rie_news_claims.id"), nullable=False),
    sa.Column("review_id", sa.Text, sa.ForeignKey("rie_news_claim_reviews.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("payload_sha256", sa.Text, nullable=False),
    sa.UniqueConstraint("claim_id", "review_id"),
)
