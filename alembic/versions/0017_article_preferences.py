"""Personal reading preferences."""
from alembic import op
from engine.models.schema_v17 import article_preferences

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    article_preferences.create(op.get_bind())


def downgrade():
    article_preferences.drop(op.get_bind())
