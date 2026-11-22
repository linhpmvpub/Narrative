"""News claim review before canonical ingestion."""

from alembic import op
from engine.models.schema_v14 import news_claim_intakes, news_claim_reviews, news_claims

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    for table in (news_claims, news_claim_reviews, news_claim_intakes):
        table.create(op.get_bind())


def downgrade():
    for table in (news_claim_intakes, news_claim_reviews, news_claims):
        table.drop(op.get_bind())
