"""P4 account and private product projections; earlier schemas remain frozen."""

import sqlalchemy as sa

from engine.models.schema_v3 import metadata as v3

metadata = sa.MetaData()
for old_table in v3.sorted_tables:
    old_table.to_metadata(metadata)


def table(name, *columns, constraints=()):
    return sa.Table("rie_" + name, metadata, *columns, *constraints)


def key(name="id", foreign=None):
    args = [sa.ForeignKey(foreign)] if foreign else []
    return sa.Column(name, sa.Text, *args, primary_key=True)


users = table(
    "users",
    key(),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("role", sa.Text, nullable=False),
    constraints=(sa.CheckConstraint("role IN ('member','admin')"),),
)
tokens = table(
    "tokens",
    key("token_hash"),
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked", sa.Boolean, nullable=False, default=False),
)
writes = table(
    "api_writes",
    key(),
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("request_hash", sa.Text, nullable=False),
    sa.Column("response", sa.JSON, nullable=False),
)
cards = table(
    "user_cards",
    key(),
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("canonical_key", sa.Text, nullable=False),
    sa.Column(
        "event_version_id",
        sa.Uuid(as_uuid=False),
        sa.ForeignKey("rie_event_versions.id"),
        nullable=False,
    ),
    sa.Column("correction_of", sa.Text, sa.ForeignKey("rie_user_cards.id")),
    constraints=(sa.UniqueConstraint("user_id", "canonical_key", "event_version_id"),),
)
card_threads = table(
    "card_threads",
    key("card_id", "rie_user_cards.id"),
    sa.Column(
        "thread_id", sa.Uuid(as_uuid=False), sa.ForeignKey("rie_subscriptions.id"), primary_key=True
    ),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("source_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("snapshot", sa.JSON, nullable=False),
)
feedback = table(
    "card_feedback",
    key(),
    sa.Column("card_id", sa.Text, sa.ForeignKey("rie_user_cards.id"), nullable=False),
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), nullable=False),
    sa.Column("label", sa.Text, nullable=False),
    sa.Column("reason", sa.Text, nullable=False),
    sa.Column("active", sa.Boolean, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    constraints=(
        sa.CheckConstraint("label IN ('USEFUL','ALREADY_KNEW','NOT_RELEVANT','UNCLEAR','WRONG')"),
    ),
)
sa.Index(
    "uq_rie_current_card_feedback",
    feedback.c.user_id,
    feedback.c.card_id,
    unique=True,
    sqlite_where=feedback.c.active.is_(True),
    postgresql_where=feedback.c.active.is_(True),
)
shares = table(
    "story_shares",
    key("token_hash"),
    sa.Column(
        "thread_id", sa.Uuid(as_uuid=False), sa.ForeignKey("rie_subscriptions.id"), nullable=False
    ),
    sa.Column("active", sa.Boolean, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
