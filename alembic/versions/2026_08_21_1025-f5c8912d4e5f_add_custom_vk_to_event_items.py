"""Add custom_vk to event_items

Revision ID: f5c8912d4e5f
Revises: e4b78912c3d4
Create Date: 2026-08-21 10:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5c8912d4e5f'
down_revision: Union[str, None] = 'e4b78912c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('event_items')]
    
    if 'custom_vk' not in columns:
        op.add_column(
            'event_items',
            sa.Column('custom_vk', sa.Numeric(10, 2), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = [col['name'] for col in insp.get_columns('event_items')]
    
    if 'custom_vk' in columns:
        op.drop_column('event_items', 'custom_vk')
