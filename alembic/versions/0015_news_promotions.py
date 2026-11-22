"""Canonical news receipts."""

from alembic import op
from engine.models.schema_v15 import news_promotions

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    news_promotions.create(op.get_bind())


def downgrade():
    news_promotions.drop(op.get_bind())
