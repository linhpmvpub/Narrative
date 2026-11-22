"""Exposure evidence review audit."""

from alembic import op
from engine.models.schema_v16 import exposure_drafts, exposure_reviews

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    for table in (exposure_drafts, exposure_reviews):
        table.create(op.get_bind())


def downgrade():
    for table in (exposure_reviews, exposure_drafts):
        table.drop(op.get_bind())
