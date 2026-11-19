"""Add origin_group and country_of_origin to catalog_items

Revision ID: 002_add_origin_group
Revises: 001_create_catalog_items
Create Date: 2026-11-19 12:45:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_origin_group'
down_revision: Union[str, None] = '001_create_catalog_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('catalog_items', sa.Column('origin_group', sa.String(length=32), nullable=True))
    op.add_column('catalog_items', sa.Column('country_of_origin', sa.String(length=64), nullable=True))
    op.create_check_constraint(
        'chk_catalog_items_origin_group',
        'catalog_items',
        "origin_group IS NULL OR origin_group IN ('domestic', 'foreign')"
    )
    op.create_index('ix_catalog_items_origin_group', 'catalog_items', ['origin_group'], unique=False)
    op.create_index('ix_catalog_origin_category_size', 'catalog_items', ['origin_group', 'category', 'size_ml'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_catalog_origin_category_size', table_name='catalog_items')
    op.drop_index('ix_catalog_items_origin_group', table_name='catalog_items')
    op.drop_constraint('chk_catalog_items_origin_group', table_name='catalog_items', type_='check')
    op.drop_column('catalog_items', 'country_of_origin')
    op.drop_column('catalog_items', 'origin_group')
