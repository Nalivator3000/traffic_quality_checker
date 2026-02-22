"""add_webmaster_status

Revision ID: c7f2a1d8e345
Revises: a1c3e9f72b44
Create Date: 2026-02-22 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c7f2a1d8e345'
down_revision: Union[str, Sequence[str], None] = 'a1c3e9f72b44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webmaster_status",
        sa.Column("webmaster", sa.String(255), primary_key=True),
        sa.Column(
            "updated_at",
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
        sa.Column("avg_approve_pct", sa.Float(), nullable=False),
        sa.Column("adj_buyout_pct", sa.Float(), nullable=False),
        sa.Column("trash_pct", sa.Float(), nullable=False),
        sa.Column("avg_trash_pct", sa.Float(), nullable=False),
        sa.Column("score_pct", sa.Float(), nullable=True),
        sa.Column(
            "issues",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "ok",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_table("webmaster_status")
