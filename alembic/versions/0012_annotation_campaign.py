"""Packet-scoped campaign participants."""

from alembic import op
from engine.models.schema_v12 import roster

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    roster.create(op.get_bind())


def downgrade():
    roster.drop(op.get_bind())
