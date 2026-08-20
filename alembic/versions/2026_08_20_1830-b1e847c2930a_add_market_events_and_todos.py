"""Add market_events, event_items and event_todos

Revision ID: b1e847c2930a
Revises: affc007960e6
Create Date: 2026-08-20 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1e847c2930a'
down_revision: Union[str, None] = 'affc007960e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = insp.get_table_names()

    # market_events
    if 'market_events' not in existing_tables:
        op.create_table(
            'market_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('event_date', sa.DateTime(), nullable=True),
            sa.Column('location', sa.String(length=255), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='planning'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_market_events_id'), 'market_events', ['id'], unique=False)

    # event_items
    if 'event_items' not in existing_tables:
        op.create_table(
            'event_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('event_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=True),
            sa.Column('custom_name', sa.String(length=255), nullable=True),
            sa.Column('target_quantity', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('produced_quantity', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['event_id'], ['market_events.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_event_items_id'), 'event_items', ['id'], unique=False)

    # event_todos
    if 'event_todos' not in existing_tables:
        op.create_table(
            'event_todos',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('event_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=True, server_default='Allgemein'),
            sa.Column('is_done', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['event_id'], ['market_events.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_event_todos_id'), 'event_todos', ['id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = insp.get_table_names()

    if 'event_todos' in existing_tables:
        op.drop_index(op.f('ix_event_todos_id'), table_name='event_todos')
        op.drop_table('event_todos')
    if 'event_items' in existing_tables:
        op.drop_index(op.f('ix_event_items_id'), table_name='event_items')
        op.drop_table('event_items')
    if 'market_events' in existing_tables:
        op.drop_index(op.f('ix_market_events_id'), table_name='market_events')
        op.drop_table('market_events')
