"""Add product_ideas to market_events

Revision ID: e4b78912c3d4
Revises: c3f912a7b8e1
Create Date: 2026-08-21 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b78912c3d4'
down_revision: Union[str, None] = 'c3f912a7b8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('market_events')]
    
    if 'product_ideas' not in columns:
        op.add_column(
            'market_events',
            sa.Column('product_ideas', sa.Text(), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('market_events')]
    
    if 'product_ideas' in columns:
        op.drop_column('market_events', 'product_ideas')
