"""Private accounts, cards and sharing."""

from alembic import op
from engine.models.schema_v3 import metadata as previous
from engine.models.schema_v4 import metadata

revision = "0004"
down_revision = "0003"
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
