"""add_agent_user_and_transcript_status

Revision ID: dd0576869e44
Revises: f117a74dad34
Create Date: 2026-02-02 22:15:44.859273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd0576869e44'
down_revision: Union[str, None] = 'f117a74dad34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Agent System User UUID (고정값)
AGENT_USER_ID = "11111111-1111-1111-1111-111111111111"


def upgrade() -> None:
    # 1. transcripts 테이블에 status 컬럼 추가
    op.add_column(
        'transcripts',
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            server_default='completed',
            comment='응답 상태 (completed/interrupted)',
        ),
    )

    # 2. users 테이블에 Agent System User 추가
    op.execute(
        f"""
        INSERT INTO users (id, email, name, auth_provider, created_at, updated_at)
        VALUES (
            '{AGENT_USER_ID}',
            'agent@system.internal',
            'AI 비서',
            'system',
            NOW(),
            NOW()
        )
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    # 1. Agent System User 삭제
    op.execute(f"DELETE FROM users WHERE id = '{AGENT_USER_ID}'")

    # 2. transcripts 테이블에서 status 컬럼 삭제
    op.drop_column('transcripts', 'status')
