"""Add is_for_market to products

Revision ID: c3f912a7b8e1
Revises: b1e847c2930a
Create Date: 2026-08-20 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f912a7b8e1'
down_revision: Union[str, None] = 'b1e847c2930a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('products')]
    
    if 'is_for_market' not in columns:
        op.add_column(
            'products',
            sa.Column('is_for_market', sa.Integer(), nullable=False, server_default='1')
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('products')]
    
    if 'is_for_market' in columns:
        op.drop_column('products', 'is_for_market')
