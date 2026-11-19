"""Create orders and order_items tables

Revision ID: 001_create_orders_schema
Revises: 
Create Date: 2026-11-15 10:50:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_create_orders_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'orders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('request_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('customer_ref', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='CREATED'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='INR'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_orders_idempotency_key', 'orders', ['idempotency_key'], unique=True)
    op.create_index('ix_orders_customer_ref', 'orders', ['customer_ref'], unique=False)

    op.create_table(
        'order_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('catalog_item_id', sa.UUID(), nullable=False),
        sa.Column('product_code', sa.String(length=64), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('size_ml', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('line_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('quantity > 0', name='chk_order_items_qty_positive'),
        sa.CheckConstraint('unit_price >= 0', name='chk_order_items_price_non_negative')
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'], unique=False)
    op.create_index('ix_order_items_catalog_item_id', 'order_items', ['catalog_item_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_order_items_catalog_item_id', table_name='order_items')
    op.drop_index('ix_order_items_order_id', table_name='order_items')
    op.drop_table('order_items')
    op.drop_index('ix_orders_customer_ref', table_name='orders')
    op.drop_index('ix_orders_idempotency_key', table_name='orders')
    op.drop_table('orders')

