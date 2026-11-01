"""Who made a drawing, and the document with its edit history

Revision ID: a7c31f2e9b10
Revises: 5d663ac08c55
Create Date: 2026-11-01 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'a7c31f2e9b10'
down_revision: Union[str, Sequence[str], None] = '5d663ac08c55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('documentmodel', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_email', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('created_by_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('state', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('documentmodel', schema=None) as batch_op:
        batch_op.drop_column('state')
        batch_op.drop_column('created_by_name')
        batch_op.drop_column('created_by_email')
