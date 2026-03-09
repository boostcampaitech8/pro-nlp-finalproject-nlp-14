"""add file_path column to meeting_transcripts

Revision ID: b2c3d4e5f6g7
Revises: 380b5e65ed84
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = '380b5e65ed84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # meeting_transcripts 테이블에 file_path 컬럼 추가
    op.add_column('meeting_transcripts', sa.Column(
        'file_path', sa.String(500), nullable=True,
        comment='MinIO에 저장된 회의록 파일 경로'
    ))


def downgrade() -> None:
    op.drop_column('meeting_transcripts', 'file_path')
