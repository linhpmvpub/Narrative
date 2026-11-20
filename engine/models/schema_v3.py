"""Frozen P3 audit additions, independent of production seed history."""

import sqlalchemy as sa

from engine.models.schema_v2 import metadata as v2

metadata = sa.MetaData()
for table in v2.sorted_tables:
    table.to_metadata(metadata)

demo_contexts = sa.Table(
    "rie_demo_contexts",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("sha256", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    ),
)
policy_traces = sa.Table(
    "rie_policy_traces",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("input_id", sa.Text, nullable=False),
    sa.Column("narrative_id", sa.Text, sa.ForeignKey("rie_narratives.id"), nullable=False),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("policy_version", sa.Text, nullable=False),
    sa.Column("trace", sa.JSON, nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    ),
)
dispatch_plans = sa.Table(
    "rie_dispatch_plans",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("user_id", sa.Text, nullable=False),
    sa.Column("canonical_key", sa.Text, nullable=False),
    sa.Column("event_version_id", sa.Text, nullable=False),
    sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("result", sa.JSON, nullable=False),
    sa.Column("delivery_status", sa.Text, nullable=False, server_default="dry_run"),
    sa.Column("sent_at", sa.DateTime(timezone=True)),
    sa.CheckConstraint("delivery_status = 'dry_run' AND sent_at IS NULL"),
    sa.UniqueConstraint("user_id", "canonical_key", "event_version_id"),
)
dispatch_users = sa.Table(
    "rie_dispatch_users",
    metadata,
    sa.Column("user_id", sa.Text, primary_key=True),
)
