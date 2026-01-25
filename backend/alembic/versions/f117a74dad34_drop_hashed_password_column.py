"""drop_hashed_password_column

Revision ID: f117a74dad34
Revises: 0430fae21780
Create Date: 2026-01-25 17:27:39.928686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f117a74dad34'
down_revision: Union[str, None] = '0430fae21780'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # OAuth 전용으로 전환하면서 hashed_password 컬럼 삭제
    op.drop_column('users', 'hashed_password')


def downgrade() -> None:
    # 롤백 시 hashed_password 컬럼 복원
    op.add_column('users', sa.Column('hashed_password', sa.String(255), nullable=True))
