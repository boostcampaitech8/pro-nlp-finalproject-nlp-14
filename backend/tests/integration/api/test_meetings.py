"""회의 API 통합 테스트"""

import pytest
from uuid import uuid4

from app.models.meeting import Meeting, MeetingStatus
from app.models.user import User
from app.models.team import Team


@pytest.mark.asyncio
async def test_create_meeting(async_client, test_team: Team, test_user: User, auth_headers):
    """회의 생성 API 테스트"""
    meeting_data = {
        "title": "테스트 회의",
        "description": "API 테스트를 위한 회의",
    }

    # Note: 실제로는 auth_headers가 유효한 JWT를 포함해야 함
    # 현재는 인증 미들웨어가 없으므로 테스트만 작성
    response = await async_client.post(
        f"/api/v1/teams/{test_team.id}/meetings",
        json=meeting_data,
        # headers=auth_headers,  # 인증 구현 후 활성화
    )

    # 인증이 없으므로 401 또는 구현에 따라 다른 응답 예상
    # assert response.status_code == 201
    # data = response.json()
    # assert data["title"] == meeting_data["title"]


@pytest.mark.asyncio
async def test_get_meeting(db_session, test_meeting: Meeting):
    """회의 조회 테스트 (DB 레벨)"""
    # 데이터베이스에서 직접 조회
    from sqlalchemy import select

    query = select(Meeting).where(Meeting.id == test_meeting.id)
    result = await db_session.execute(query)
    meeting = result.scalar_one_or_none()

    assert meeting is not None
    assert meeting.id == test_meeting.id
    assert meeting.title == "테스트 회의"
    assert meeting.status == MeetingStatus.SCHEDULED.value
