"""Isolated real-source staging and immutable extraction review history."""

import sqlalchemy as sa

from engine.models.schema_v4 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)

filings = sa.Table(
    "rie_sec_filings",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("ticker", sa.Text, nullable=False),
    sa.Column("accession", sa.Text, nullable=False, unique=True),
    sa.Column("source_url", sa.Text, nullable=False),
    sa.Column("content_sha256", sa.Text, nullable=False),
    sa.Column("text_sha256", sa.Text, nullable=False),
    sa.Column("source_text", sa.Text, nullable=False),
    sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("manifest", sa.JSON, nullable=False),
    sa.Column("revision", sa.Integer, nullable=False, default=0),
)
drafts = sa.Table(
    "rie_sec_drafts",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("filing_id", sa.Text, sa.ForeignKey(filings.c.id), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("author_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("canonical_key", sa.Text, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.UniqueConstraint("filing_id", "version"),
)
reviews = sa.Table(
    "rie_sec_reviews",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("draft_id", sa.Text, sa.ForeignKey(drafts.c.id), nullable=False, unique=True),
    sa.Column("reviewer_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("decision", sa.Text, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.CheckConstraint("decision IN ('approved','rejected')"),
)
