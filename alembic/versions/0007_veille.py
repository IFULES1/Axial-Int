"""P7 — veille intelligente : skills, run history, rss feeds

Revision ID: 0007_veille
Revises: 0006_dev_users
Create Date: 2026-08-14
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_veille"
down_revision: str | None = "0006_dev_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Watch: specialised skill + rolling cumulative memory ---
    op.add_column("watches", sa.Column("skill", sa.String(length=48), nullable=False,
                                       server_default="concurrentielle"))
    op.add_column("watches", sa.Column("rolling_state", sa.Text(), nullable=True))

    # --- WatchRun: dated finding history + memory snapshot ---
    op.create_table(
        "watch_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("watch_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("delta_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("full_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("rolling_state", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.JSONB(), nullable=True),
        sa.Column("new_article_urls", postgresql.JSONB(), nullable=True),
        sa.Column("had_changes", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["watch_id"], ["watches.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_watch_runs_watch_id", "watch_runs", ["watch_id"])
    op.create_index("ix_watch_runs_created_at", "watch_runs", ["created_at"])

    # --- RssFeed: article sources agents combine with web search ---
    op.create_table(
        "rss_feeds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("category", sa.String(length=48), nullable=False, server_default="general"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_rss_feeds_user_id", "rss_feeds", ["user_id"])
    op.create_index("ix_rss_feeds_category", "rss_feeds", ["category"])


def downgrade() -> None:
    op.drop_index("ix_rss_feeds_category", table_name="rss_feeds")
    op.drop_index("ix_rss_feeds_user_id", table_name="rss_feeds")
    op.drop_table("rss_feeds")
    op.drop_index("ix_watch_runs_created_at", table_name="watch_runs")
    op.drop_index("ix_watch_runs_watch_id", table_name="watch_runs")
    op.drop_table("watch_runs")
    op.drop_column("watches", "rolling_state")
    op.drop_column("watches", "skill")
