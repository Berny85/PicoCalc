"""Restructure SalesOrder for multiple items

Revision ID: c60b9d0af80e
Revises: 543d8d9f5f22
Create Date: 2026-02-22 13:59:06.874277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c60b9d0af80e'
down_revision: Union[str, None] = '543d8d9f5f22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tabelle sales_order_items existiert bereits (von SQLAlchemy erstellt)
    # Nur alte Felder aus sales_orders entfernen
    op.drop_column('sales_orders', 'product_id')
    op.drop_column('sales_orders', 'quantity')
    op.drop_column('sales_orders', 'unit_price')
    op.drop_column('sales_orders', 'production_cost_per_unit')


def downgrade() -> None:
    # Alte Felder wieder hinzufügen
    op.add_column('sales_orders', sa.Column('product_id', sa.Integer(), nullable=False))
    op.add_column('sales_orders', sa.Column('quantity', sa.Integer(), nullable=True, default=1))
    op.add_column('sales_orders', sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False))
    op.add_column('sales_orders', sa.Column('production_cost_per_unit', sa.Numeric(precision=10, scale=2), nullable=False))
