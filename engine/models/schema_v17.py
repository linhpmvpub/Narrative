"""Account-owned article reading preferences, separate from evidence quality."""
import sqlalchemy as sa

from engine.models.schema_v16 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)
article_preferences = sa.Table(
    "rie_article_preferences", metadata,
    sa.Column("user_id", sa.Text, sa.ForeignKey("rie_users.id"), primary_key=True),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("version > 0"),
)
