"""Update models-1..

Revision ID: 8729e1150f17
Revises: 48781bcbd32a
Create Date: 2025-04-16 11:41:59.181548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8729e1150f17'
down_revision: Union[str, None] = '48781bcbd32a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
