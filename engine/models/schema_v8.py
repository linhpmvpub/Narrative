"""Versioned, source-backed SEC financial comparisons (development scope)."""

import sqlalchemy as sa

from engine.models.schema_v7 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)
financial_snapshots = sa.Table(
    "rie_financial_snapshots",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("ticker", sa.Text, nullable=False),
    sa.Column("cik", sa.Text, nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("capture_sha256", sa.Text, nullable=False),
    sa.Column("source_url", sa.Text, nullable=False),
    sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.UniqueConstraint("ticker", "version"),
)
