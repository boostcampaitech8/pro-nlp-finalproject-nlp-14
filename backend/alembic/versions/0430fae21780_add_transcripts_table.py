"""add transcripts table

Revision ID: 0430fae21780
Revises: fa12da308ae8
Create Date: 2026-01-22 18:05:24.619834

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0430fae21780"
down_revision: Union[str, None] = "fa12da308ae8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("meeting_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False, comment="발화 시작 시간 (밀리초)"),
        sa.Column("end_ms", sa.Integer(), nullable=False, comment="발화 종료 시간 (밀리초)"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True, comment="발화 시작 타임스탬프 (절대시간)"),
        sa.Column("transcript_text", sa.Text(), nullable=False, comment="전사된 텍스트"),
        sa.Column("confidence", sa.Float(), nullable=False, comment="평균 신뢰도"),
        sa.Column("min_confidence", sa.Float(), nullable=False, comment="최소 신뢰도"),
        sa.Column("agent_call", sa.Boolean(), nullable=False, comment="에이전트 호출 여부"),
        sa.Column("agent_call_keyword", sa.String(length=50), nullable=True, comment="에이전트 호출 키워드"),
        sa.Column("agent_call_confidence", sa.Float(), nullable=True, comment="에이전트 호출 키워드 신뢰도"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transcripts_meeting_id"), "transcripts", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_transcripts_user_id"), "transcripts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_transcripts_user_id"), table_name="transcripts")
    op.drop_index(op.f("ix_transcripts_meeting_id"), table_name="transcripts")
    op.drop_table("transcripts")
