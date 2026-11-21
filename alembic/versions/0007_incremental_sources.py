"""Incremental source reconciliation receipts."""
from alembic import op
from engine.models.schema_v6 import metadata as previous
from engine.models.schema_v7 import metadata

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    for table in metadata.sorted_tables:
        if table.name not in previous.tables:
            table.create(op.get_bind())


def downgrade():
    for table in reversed(metadata.sorted_tables):
        if table.name not in previous.tables:
            table.drop(op.get_bind())
