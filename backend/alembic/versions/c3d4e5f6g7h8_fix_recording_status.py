"""Fix recording status for uploaded files

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-01-10 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # file_path가 있는 녹음을 COMPLETED로 업데이트
    # (MinIO에 업로드되었지만 confirm이 실패한 경우)
    op.execute("""
        UPDATE meeting_recordings
        SET status = 'completed'
        WHERE status IN ('pending', 'recording')
        AND file_path IS NOT NULL
        AND file_path != ''
    """)


def downgrade() -> None:
    # 롤백 시 원래 상태로 돌릴 방법이 없으므로 pass
    pass
