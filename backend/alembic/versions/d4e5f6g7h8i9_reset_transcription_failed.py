"""Reset transcription_failed recordings to completed

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2025-01-10 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # transcription_failed 상태를 completed로 변경
    op.execute("""
        UPDATE meeting_recordings
        SET status = 'completed'
        WHERE status = 'transcription_failed'
    """)


def downgrade() -> None:
    pass
