"""SEC staging, extraction versions and independent review receipts."""

from alembic import op
from engine.models.schema_v4 import metadata as previous
from engine.models.schema_v5 import metadata

revision = "0005"
down_revision = "0004"
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
