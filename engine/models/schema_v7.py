"""Incremental source checkpoints and immutable collection receipts."""

import sqlalchemy as sa

from engine.models.schema_v6 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)

source_cursors = sa.Table(
    "rie_source_cursors",
    metadata,
    sa.Column("ticker", sa.Text, primary_key=True),
    sa.Column("cik", sa.Text, nullable=False),
    sa.Column("floor_date", sa.Date, nullable=False),
    sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("snapshot_hash", sa.Text, nullable=False),
)
collection_runs = sa.Table(
    "rie_collection_runs",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("ticker", sa.Text, nullable=False),
    sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("result", sa.JSON, nullable=False),
)
