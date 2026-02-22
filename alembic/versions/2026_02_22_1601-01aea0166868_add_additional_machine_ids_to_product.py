"""Add additional_machine_ids to Product

Revision ID: 01aea0166868
Revises: 4343c4224797
Create Date: 2026-02-22 16:01:23.874277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01aea0166868'
down_revision: Union[str, None] = '4343c4224797'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add additional_machine_ids column
    op.add_column('products', sa.Column('additional_machine_ids', sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove additional_machine_ids column
    op.drop_column('products', 'additional_machine_ids')
