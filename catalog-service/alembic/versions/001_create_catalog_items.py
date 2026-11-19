"""Create catalog items table and indexes

Revision ID: 001_create_catalog_items
Revises: 
Create Date: 2026-11-15 10:45:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_create_catalog_items'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'catalog_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('product_code', sa.String(length=64), nullable=False),
        sa.Column('supplier_code', sa.String(length=32), nullable=False),
        sa.Column('brand_code', sa.String(length=32), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('subcategory', sa.String(length=64), nullable=True),
        sa.Column('size_ml', sa.Integer(), nullable=False),
        sa.Column('size_code', sa.String(length=16), nullable=False),
        sa.Column('mrp', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='INR'),
        sa.Column('image_key', sa.String(length=255), nullable=True),
        sa.Column('source_date', sa.Date(), nullable=False),
        sa.Column('source_page', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('size_ml > 0', name='chk_catalog_items_size_positive'),
        sa.CheckConstraint('mrp >= 0', name='chk_catalog_items_mrp_non_negative')
    )
    op.create_index('ix_catalog_items_product_code', 'catalog_items', ['product_code'], unique=True)
    op.create_index('ix_catalog_items_brand_code', 'catalog_items', ['brand_code'], unique=False)
    op.create_index('ix_catalog_items_product_name', 'catalog_items', ['product_name'], unique=False)
    op.create_index('ix_catalog_items_category', 'catalog_items', ['category'], unique=False)
    op.create_index('ix_catalog_category_size', 'catalog_items', ['category', 'size_ml'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_catalog_category_size', table_name='catalog_items')
    op.drop_index('ix_catalog_items_category', table_name='catalog_items')
    op.drop_index('ix_catalog_items_product_name', table_name='catalog_items')
    op.drop_index('ix_catalog_items_brand_code', table_name='catalog_items')
    op.drop_index('ix_catalog_items_product_code', table_name='catalog_items')
    op.drop_table('catalog_items')

