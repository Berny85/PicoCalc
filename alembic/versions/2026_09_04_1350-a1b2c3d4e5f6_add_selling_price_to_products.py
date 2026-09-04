"""Add selling_price to products

Revision ID: a1b2c3d4e5f6
Revises: f5c8912d4e5f
Create Date: 2026-09-04 13:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f5c8912d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('products')]
    
    if 'selling_price' not in columns:
        op.add_column(
            'products',
            sa.Column('selling_price', sa.Numeric(10, 2), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('products')]
    
    if 'selling_price' in columns:
        op.drop_column('products', 'selling_price')
