"""merge heads

Revision ID: 8d812817ec16
Revises: dd0576869e44, e5f6g7h8i9j0
Create Date: 2026-02-04 13:57:13.760536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d812817ec16'
down_revision: Union[str, None] = ('dd0576869e44', 'e5f6g7h8i9j0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
