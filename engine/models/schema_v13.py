"""Independent market news inbox; no automatic economic events or graph approvals."""

import sqlalchemy as sa

from engine.models.schema_v12 import metadata as previous

metadata = sa.MetaData()
for old in previous.sorted_tables:
    old.to_metadata(metadata)

news_sources = sa.Table(
    "rie_news_sources",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("config", sa.JSON, nullable=False),
    sa.Column("state", sa.JSON, nullable=False),
    sa.Column("next_poll_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("lease_until", sa.DateTime(timezone=True)),
    sa.Column("lease_id", sa.Text),
    sa.Column("last_attempt", sa.DateTime(timezone=True)),
    sa.Column("last_success", sa.DateTime(timezone=True)),
    sa.Column("last_status", sa.Text, nullable=False),
    sa.Column("failures", sa.Integer, nullable=False),
)
news_items = sa.Table(
    "rie_news_items",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("source_id", sa.Text, sa.ForeignKey("rie_news_sources.id"), nullable=False),
    sa.Column("external_id", sa.Text, nullable=False),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("content_sha256", sa.Text, nullable=False),
    sa.Column("article_key", sa.Text, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.UniqueConstraint("source_id", "external_id"),
)
news_revisions = sa.Table(
    "rie_news_revisions",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("item_id", sa.Text, sa.ForeignKey("rie_news_items.id"), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("capture_sha256", sa.Text, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.UniqueConstraint("item_id", "version"),
)
sa.Index("ix_news_first_seen", news_items.c.first_seen_at, news_items.c.id)
