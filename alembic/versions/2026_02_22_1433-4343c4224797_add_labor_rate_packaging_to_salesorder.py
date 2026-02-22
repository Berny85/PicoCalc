"""Add labor_rate_packaging to SalesOrder

Revision ID: 4343c4224797
Revises: c60b9d0af80e
Create Date: 2026-02-22 14:33:44.874277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4343c4224797'
down_revision: Union[str, None] = 'c60b9d0af80e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add labor_rate_packaging column with default 20.00
    op.add_column('sales_orders', sa.Column('labor_rate_packaging', sa.Numeric(precision=10, scale=2), nullable=True, server_default='20.00'))


def downgrade() -> None:
    # Remove labor_rate_packaging column
    op.drop_column('sales_orders', 'labor_rate_packaging')
