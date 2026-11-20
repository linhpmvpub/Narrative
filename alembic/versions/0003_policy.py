"""Immutable demo contexts, decision traces and dry-run dispatch plans."""

from alembic import op
from engine.models.schema_v3 import demo_contexts, dispatch_plans, dispatch_users, policy_traces

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    for table in (demo_contexts, policy_traces, dispatch_plans, dispatch_users):
        table.create(op.get_bind())


def downgrade():
    for table in (dispatch_users, dispatch_plans, policy_traces, demo_contexts):
        table.drop(op.get_bind())
