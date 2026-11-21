"""Frozen predictions and revision-bound independent adjudications."""

import sqlalchemy as sa

from engine.models.schema_v10 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)
predictions = sa.Table(
    "rie_frozen_predictions",
    metadata,
    sa.Column("packet_id", sa.Text, sa.ForeignKey("rie_annotation_packets.id"), primary_key=True),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("sha256", sa.Text, nullable=False),
    sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
)
adjudications = sa.Table(
    "rie_annotation_adjudications",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("packet_id", sa.Text, nullable=False),
    sa.Column("case_id", sa.Text, nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("vote_hash", sa.Text, nullable=False),
    sa.Column("reviewer_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(
        ["packet_id", "case_id"], ["rie_annotation_cases.packet_id", "rie_annotation_cases.id"]
    ),
    sa.UniqueConstraint("packet_id", "case_id", "version"),
)
