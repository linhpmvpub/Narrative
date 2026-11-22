"""Market news inbox and durable collector state."""

from alembic import op
from engine.models.schema_v13 import news_items, news_revisions, news_sources

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    for table in (news_sources, news_items, news_revisions):
        table.create(op.get_bind())


def downgrade():
    for table in (news_revisions, news_items, news_sources):
        table.drop(op.get_bind())
