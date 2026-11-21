"""Packet-scoped annotation campaign roster."""

import sqlalchemy as sa

from engine.models.schema_v11 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)
roster = sa.Table(
    "rie_annotation_roster",
    metadata,
    sa.Column("packet_id", sa.Text, sa.ForeignKey("rie_annotation_packets.id"), primary_key=True),
    sa.Column("slot", sa.Text, primary_key=True),
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("slot IN ('reviewer_a','reviewer_b','adjudicator')"),
    sa.UniqueConstraint("packet_id", "user_id"),
)
