"""create_leads_table

Revision ID: b589e261f68f
Revises:
Create Date: 2026-02-22 19:08:43.450743

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b589e261f68f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id_custom", sa.BigInteger(), primary_key=True),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("webmaster", sa.String(255), nullable=False),
        sa.Column("sum", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_leads_date", "leads", ["date"])
    op.create_index("ix_leads_webmaster", "leads", ["webmaster"])


def downgrade() -> None:
    op.drop_index("ix_leads_webmaster", table_name="leads")
    op.drop_index("ix_leads_date", table_name="leads")
    op.drop_table("leads")
