"""add transcript fields to recordings and meeting_transcripts table

Revision ID: a1b2c3d4e5f6
Revises: 485a5c552d13
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '485a5c552d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MeetingRecording 테이블에 STT 관련 필드 추가
    op.add_column('meeting_recordings', sa.Column(
        'transcript_text', sa.Text(), nullable=True,
        comment='STT 변환된 전체 텍스트'
    ))
    op.add_column('meeting_recordings', sa.Column(
        'transcript_segments', postgresql.JSONB(), nullable=True,
        comment='타임스탬프 포함 세그먼트 JSON'
    ))
    op.add_column('meeting_recordings', sa.Column(
        'transcript_language', sa.String(10), nullable=True,
        comment='감지된 언어 코드 (ko, en 등)'
    ))
    op.add_column('meeting_recordings', sa.Column(
        'transcription_started_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('meeting_recordings', sa.Column(
        'transcription_completed_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('meeting_recordings', sa.Column(
        'transcription_error', sa.Text(), nullable=True,
        comment='STT 실패 시 에러 메시지'
    ))

    # MeetingTranscript 테이블 생성
    op.create_table(
        'meeting_transcripts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('meeting_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('meetings.id'), nullable=False, unique=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('full_text', sa.Text(), nullable=True,
                  comment='전체 텍스트 (화자 라벨 포함)'),
        sa.Column('utterances', postgresql.JSONB(), nullable=True,
                  comment='화자별 발화 목록'),
        sa.Column('total_duration_ms', sa.Integer(), nullable=True),
        sa.Column('speaker_count', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True,
                  comment='실패 시 에러 메시지'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # MeetingTranscript 테이블 삭제
    op.drop_table('meeting_transcripts')

    # MeetingRecording 테이블에서 STT 관련 필드 삭제
    op.drop_column('meeting_recordings', 'transcription_error')
    op.drop_column('meeting_recordings', 'transcription_completed_at')
    op.drop_column('meeting_recordings', 'transcription_started_at')
    op.drop_column('meeting_recordings', 'transcript_language')
    op.drop_column('meeting_recordings', 'transcript_segments')
    op.drop_column('meeting_recordings', 'transcript_text')
