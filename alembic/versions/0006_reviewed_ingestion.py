"""Explicit source permissions and reviewed-ingestion receipts."""

from alembic import op
from engine.models.schema_v5 import metadata as previous
from engine.models.schema_v6 import metadata

revision = "0006"
down_revision = "0005"
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
