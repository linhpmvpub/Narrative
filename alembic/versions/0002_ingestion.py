"""Isolated synthetic databases and idempotent ingestion receipts."""

from alembic import op
from engine.models.schema_v2 import database_mode, ingestion_receipts

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    database_mode.create(op.get_bind())
    ingestion_receipts.create(op.get_bind())


def downgrade():
    ingestion_receipts.drop(op.get_bind())
    database_mode.drop(op.get_bind())
