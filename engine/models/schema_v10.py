"""Frozen blind annotation assignments and immutable human label revisions."""

import sqlalchemy as sa

from engine.models.schema_v9 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)
packets = sa.Table(
    "rie_annotation_packets",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("case_count", sa.Integer, nullable=False),
)
cases = sa.Table(
    "rie_annotation_cases",
    metadata,
    sa.Column("packet_id", sa.Text, sa.ForeignKey(packets.c.id), primary_key=True),
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("payload", sa.JSON, nullable=False),
)
assignments = sa.Table(
    "rie_annotation_assignments",
    metadata,
    sa.Column("packet_id", sa.Text, sa.ForeignKey(packets.c.id), primary_key=True),
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), primary_key=True),
)
labels = sa.Table(
    "rie_annotation_labels",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("packet_id", sa.Text, nullable=False),
    sa.Column("case_id", sa.Text, nullable=False),
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(["packet_id", "case_id"], [cases.c.packet_id, cases.c.id]),
    sa.UniqueConstraint("packet_id", "case_id", "user_id", "version"),
)
corroborations = sa.Table(
    "rie_corroboration_versions",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("version", sa.Integer, nullable=False, unique=True),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
)
