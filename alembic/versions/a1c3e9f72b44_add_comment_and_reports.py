"""add_comment_and_reports

Revision ID: a1c3e9f72b44
Revises: b589e261f68f
Create Date: 2026-02-22 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1c3e9f72b44'
down_revision: Union[str, Sequence[str], None] = 'b589e261f68f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add comment column to leads
    op.add_column("leads", sa.Column("comment", sa.Text(), nullable=True))

    # Create webmaster_reports table
    op.create_table(
        "webmaster_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("webmaster", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("leads_total", sa.Integer(), nullable=False),
        sa.Column("approved", sa.Integer(), nullable=False),
        sa.Column("bought_out", sa.Integer(), nullable=False),
        sa.Column("trash", sa.Integer(), nullable=False),
        sa.Column("approve_pct", sa.Float(), nullable=False),
        sa.Column("buyout_pct", sa.Float(), nullable=False),
        sa.Column("trash_pct", sa.Float(), nullable=False),
        sa.Column("score_pct", sa.Float(), nullable=True),
        sa.Column(
            "issues",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.create_index("ix_webmaster_reports_webmaster", "webmaster_reports", ["webmaster"])


def downgrade() -> None:
    op.drop_index("ix_webmaster_reports_webmaster", table_name="webmaster_reports")
    op.drop_table("webmaster_reports")
    op.drop_column("leads", "comment")
