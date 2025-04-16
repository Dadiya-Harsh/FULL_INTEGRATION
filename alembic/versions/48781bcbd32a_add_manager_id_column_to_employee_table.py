"""Add manager_id column to employee table

Revision ID: 48781bcbd32a
Revises: ff0827167778
Create Date: 2025-04-16 11:21:13.755687

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48781bcbd32a'
down_revision: Union[str, None] = 'ff0827167778'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
   with op.batch_alter_table('employee') as batch_op:
        batch_op.add_column(sa.Column('manager_id', sa.Integer(), sa.ForeignKey('employee.id'), nullable=True))


def downgrade():
    with op.batch_alter_table('employee') as batch_op:
        batch_op.drop_column('manager_id')
