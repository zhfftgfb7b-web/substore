"""add product_waitlist table

Revision ID: 002
Revises: 001
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create product_waitlist table"""
    op.create_table(
        'product_waitlist',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('requested_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('notified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    )

    # Indexes for performance
    op.create_index('ix_product_waitlist_user_id', 'product_waitlist', ['user_id'])
    op.create_index('ix_product_waitlist_product_id', 'product_waitlist', ['product_id'])


def downgrade() -> None:
    """Drop product_waitlist table"""
    op.drop_index('ix_product_waitlist_product_id', table_name='product_waitlist')
    op.drop_index('ix_product_waitlist_user_id', table_name='product_waitlist')
    op.drop_table('product_waitlist')
