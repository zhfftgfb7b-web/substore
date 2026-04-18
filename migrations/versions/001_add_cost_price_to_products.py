"""add cost_price to products

Revision ID: 001
Revises:
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cost_price column to products table"""
    op.add_column('products', sa.Column('cost_price', sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    """Remove cost_price column from products table"""
    op.drop_column('products', 'cost_price')
