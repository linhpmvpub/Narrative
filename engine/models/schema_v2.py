"""P2 additions; the frozen v1 migration remains unchanged."""

import sqlalchemy as sa

from engine.models.schema_v1 import metadata as v1

metadata = sa.MetaData()
for table in v1.sorted_tables:
    table.to_metadata(metadata)

database_mode = sa.Table(
    "rie_database_mode",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("mode", sa.Text, nullable=False),
    sa.CheckConstraint("id = 1 AND mode IN ('production','synthetic')"),
)
ingestion_receipts = sa.Table(
    "rie_ingestion_receipts",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("input_id", sa.Text, nullable=False, index=True),
    sa.Column("input_sha256", sa.Text, nullable=False),
    sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("reason", sa.Text, nullable=False),
    sa.Column("event_version_id", sa.Uuid(as_uuid=False), sa.ForeignKey("rie_event_versions.id")),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    ),
    sa.UniqueConstraint("input_id", "as_of"),
)
