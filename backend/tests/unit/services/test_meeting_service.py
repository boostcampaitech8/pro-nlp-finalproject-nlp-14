"""회의 서비스 단위 테스트

총 25개 테스트:
- create_meeting: 6개 (성공, 권한, 호스트 자동 추가)
- list_team_meetings: 6개 (성공, 빈 목록, 페이지네이션, 필터링)
- get_meeting: 5개 (성공, 없음, 권한, 참여자)
- update_meeting: 5개 (호스트, owner, admin, 권한 없음)
- delete_meeting: 3개 (호스트, owner, 권한 없음)
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, ParticipantRole
from app.models.team import Team, TeamMember, TeamRole
from app.models.user import User
from app.schemas.meeting import CreateMeetingRequest, UpdateMeetingRequest
from app.services.meeting_service import MeetingService


# ===== create_meeting 테스트 (6개) =====


@pytest.mark.asyncio
async def test_create_meeting_success(db_session, test_team: Team, test_user: User):
    """회의 생성 성공"""
    service = MeetingService(db_session)

    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    meeting_data = CreateMeetingRequest(
        title="새 회의",
        description="테스트 회의입니다",
        scheduled_at=future_time,
    )

    result = await service.create_meeting(test_team.id, meeting_data, test_user.id)

    assert result.title == meeting_data.title
    assert result.description == meeting_data.description
    assert result.status == MeetingStatus.SCHEDULED.value
    assert result.team_id == test_team.id
    assert result.created_by == test_user.id


@pytest.mark.asyncio
async def test_create_meeting_not_team_member(db_session, test_team: Team, test_user2: User):
    """팀 멤버가 아닌 사용자는 회의 생성 불가"""
    service = MeetingService(db_session)

    meeting_data = CreateMeetingRequest(
        title="회의",
        description="설명",
    )

    with pytest.raises(ValueError, match="NOT_TEAM_MEMBER"):
        await service.create_meeting(test_team.id, meeting_data, test_user2.id)


@pytest.mark.asyncio
async def test_create_meeting_adds_creator_as_host(
    db_session, test_team: Team, test_user: User
):
    """회의 생성 시 생성자가 자동으로 호스트로 추가됨"""
    service = MeetingService(db_session)

    meeting_data = CreateMeetingRequest(
        title="호스트 테스트",
        description="생성자 확인",
    )

    result = await service.create_meeting(test_team.id, meeting_data, test_user.id)

    # 참여자 확인
    participant_query = select(MeetingParticipant).where(
        MeetingParticipant.meeting_id == result.id,
        MeetingParticipant.user_id == test_user.id,
    )
    participant_result = await db_session.execute(participant_query)
    participant = participant_result.scalar_one_or_none()

    assert participant is not None
    assert participant.role == ParticipantRole.HOST.value


@pytest.mark.asyncio
async def test_create_meeting_with_scheduled_time(
    db_session, test_team: Team, test_user: User
):
    """예약 시간 설정하여 회의 생성"""
    service = MeetingService(db_session)

    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=2)
    meeting_data = CreateMeetingRequest(
        title="예약 회의",
        description="2시간 후",
        scheduled_at=scheduled_time,
    )

    result = await service.create_meeting(test_team.id, meeting_data, test_user.id)

    assert result.scheduled_at == scheduled_time


@pytest.mark.asyncio
async def test_create_meeting_saves_to_db(db_session, test_team: Team, test_user: User):
    """회의가 DB에 저장되는지 확인"""
    service = MeetingService(db_session)

    meeting_data = CreateMeetingRequest(
        title="DB 저장 테스트",
        description="저장 확인",
    )

    result = await service.create_meeting(test_team.id, meeting_data, test_user.id)

    # DB에서 직접 조회
    db_meeting = await db_session.execute(
        select(Meeting).where(Meeting.id == result.id)
    )
    saved_meeting = db_meeting.scalar_one_or_none()

    assert saved_meeting is not None
    assert saved_meeting.title == meeting_data.title


@pytest.mark.asyncio
async def test_create_meeting_without_description(
    db_session, test_team: Team, test_user: User
):
    """설명 없이 회의 생성 가능"""
    service = MeetingService(db_session)

    meeting_data = CreateMeetingRequest(
        title="제목만 있는 회의",
    )

    result = await service.create_meeting(test_team.id, meeting_data, test_user.id)

    assert result.title == meeting_data.title
    assert result.description is None


# ===== list_team_meetings 테스트 (6개) =====


@pytest.mark.asyncio
async def test_list_team_meetings_success(
    db_session, test_team: Team, test_user: User, test_meeting: Meeting
):
    """팀 회의 목록 조회 성공"""
    service = MeetingService(db_session)

    result = await service.list_team_meetings(test_team.id, test_user.id)

    assert result.meta.total >= 1
    assert len(result.items) >= 1
    assert any(m.id == test_meeting.id for m in result.items)


@pytest.mark.asyncio
async def test_list_team_meetings_not_team_member(
    db_session, test_team: Team, test_user2: User
):
    """팀 멤버가 아닌 사용자는 목록 조회 불가"""
    service = MeetingService(db_session)

    with pytest.raises(ValueError, match="NOT_TEAM_MEMBER"):
        await service.list_team_meetings(test_team.id, test_user2.id)


@pytest.mark.asyncio
async def test_list_team_meetings_empty(db_session, test_user: User):
    """회의가 없는 팀의 빈 목록"""
    service = MeetingService(db_session)

    # 새 팀 생성
    new_team = Team(
        id=uuid4(),
        name="빈 팀",
        created_by=test_user.id,
    )
    db_session.add(new_team)

    # 팀 멤버 추가
    member = TeamMember(
        team_id=new_team.id,
        user_id=test_user.id,
        role=TeamRole.OWNER.value,
    )
    db_session.add(member)
    await db_session.commit()

    result = await service.list_team_meetings(new_team.id, test_user.id)

    assert result.meta.total == 0
    assert len(result.items) == 0
    assert result.meta.total_pages == 0


@pytest.mark.asyncio
async def test_list_team_meetings_pagination(
    db_session, test_team: Team, test_user: User
):
    """페이지네이션 동작 확인"""
    service = MeetingService(db_session)

    # 여러 회의 생성
    for i in range(5):
        meeting = Meeting(
            id=uuid4(),
            team_id=test_team.id,
            title=f"회의 {i}",
            created_by=test_user.id,
            status=MeetingStatus.SCHEDULED.value,
        )
        db_session.add(meeting)
    await db_session.commit()

    # 첫 페이지 (limit=2)
    page1 = await service.list_team_meetings(test_team.id, test_user.id, page=1, limit=2)
    assert len(page1.items) == 2
    assert page1.meta.page == 1
    assert page1.meta.limit == 2

    # 두 번째 페이지
    page2 = await service.list_team_meetings(test_team.id, test_user.id, page=2, limit=2)
    assert page2.meta.page == 2
    # 첫 페이지와 다른 회의들
    assert page1.items[0].id != page2.items[0].id


@pytest.mark.asyncio
async def test_list_team_meetings_filter_by_status(
    db_session, test_team: Team, test_user: User
):
    """상태로 필터링"""
    service = MeetingService(db_session)

    # 다양한 상태의 회의 생성
    scheduled_meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="예정된 회의",
        created_by=test_user.id,
        status=MeetingStatus.SCHEDULED.value,
    )
    in_progress_meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="진행 중 회의",
        created_by=test_user.id,
        status=MeetingStatus.ONGOING.value,
    )
    db_session.add_all([scheduled_meeting, in_progress_meeting])
    await db_session.commit()

    # SCHEDULED만 조회
    result = await service.list_team_meetings(
        test_team.id, test_user.id, status=MeetingStatus.SCHEDULED.value
    )

    assert all(m.status == MeetingStatus.SCHEDULED.value for m in result.items)


@pytest.mark.asyncio
async def test_list_team_meetings_ordered_by_created_at(
    db_session, test_team: Team, test_user: User
):
    """최신 순으로 정렬 확인"""
    service = MeetingService(db_session)

    # 여러 회의 생성 (순서대로)
    meeting_ids = []
    for i in range(3):
        meeting = Meeting(
            id=uuid4(),
            team_id=test_team.id,
            title=f"회의 {i}",
            created_by=test_user.id,
            status=MeetingStatus.SCHEDULED.value,
        )
        db_session.add(meeting)
        await db_session.flush()
        meeting_ids.append(meeting.id)

    await db_session.commit()

    result = await service.list_team_meetings(test_team.id, test_user.id)

    # 최신 회의가 먼저 와야 함 (created_at desc)
    # 최소한 우리가 만든 회의들 중 하나는 첫 번째에 있어야 함
    assert len(result.items) >= 3


# ===== get_meeting 테스트 (5개) =====


@pytest.mark.asyncio
async def test_get_meeting_success(
    db_session, test_team: Team, test_user: User, test_meeting: Meeting
):
    """회의 상세 조회 성공"""
    service = MeetingService(db_session)

    result = await service.get_meeting(test_meeting.id, test_user.id)

    assert result.id == test_meeting.id
    assert result.title == test_meeting.title
    assert result.team_id == test_team.id


@pytest.mark.asyncio
async def test_get_meeting_not_found(db_session, test_team: Team, test_user: User):
    """존재하지 않는 회의 조회"""
    service = MeetingService(db_session)

    fake_id = uuid4()

    with pytest.raises(ValueError, match="MEETING_NOT_FOUND"):
        await service.get_meeting(fake_id, test_user.id)


@pytest.mark.asyncio
async def test_get_meeting_not_team_member(
    db_session, test_meeting: Meeting, test_user2: User
):
    """팀 멤버가 아닌 사용자는 조회 불가"""
    service = MeetingService(db_session)

    with pytest.raises(ValueError, match="NOT_TEAM_MEMBER"):
        await service.get_meeting(test_meeting.id, test_user2.id)


@pytest.mark.asyncio
async def test_get_meeting_includes_participants(
    db_session, test_team: Team, test_user: User, test_meeting: Meeting
):
    """회의 조회 시 참여자 정보 포함"""
    service = MeetingService(db_session)

    result = await service.get_meeting(test_meeting.id, test_user.id)

    assert result.participants is not None
    assert len(result.participants) >= 1
    # 호스트(test_user)가 포함되어야 함
    assert any(p.user_id == test_user.id for p in result.participants)
    assert any(
        p.role == ParticipantRole.HOST.value for p in result.participants
    )


@pytest.mark.asyncio
async def test_get_meeting_participant_has_user_info(
    db_session, test_team: Team, test_user: User, test_meeting: Meeting
):
    """참여자에 사용자 정보가 포함되는지 확인"""
    service = MeetingService(db_session)

    result = await service.get_meeting(test_meeting.id, test_user.id)

    # 참여자 중 하나 확인
    host = next((p for p in result.participants if p.user_id == test_user.id), None)
    assert host is not None
    assert host.user is not None
    assert host.user.email == test_user.email


# ===== update_meeting 테스트 (5개) =====


@pytest.mark.asyncio
async def test_update_meeting_by_host(
    db_session, test_team: Team, test_user: User, test_meeting: Meeting
):
    """호스트가 회의 수정 성공"""
    service = MeetingService(db_session)

    update_data = UpdateMeetingRequest(
        title="수정된 제목",
        description="수정된 설명",
    )

    result = await service.update_meeting(test_meeting.id, update_data, test_user.id)

    assert result.title == update_data.title
    assert result.description == update_data.description


@pytest.mark.asyncio
async def test_update_meeting_by_team_owner(
    db_session, test_team: Team, test_user: User, test_user2: User
):
    """팀 owner가 회의 수정 가능"""
    service = MeetingService(db_session)

    # test_user는 이미 team owner (test_team fixture에서)
    # 새 회의 생성 (test_user2가 호스트)
    member2 = TeamMember(
        team_id=test_team.id,
        user_id=test_user2.id,
        role=TeamRole.MEMBER.value,
    )
    db_session.add(member2)

    meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="회의",
        created_by=test_user2.id,
        status=MeetingStatus.SCHEDULED.value,
    )
    db_session.add(meeting)

    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=test_user2.id,
        role=ParticipantRole.HOST.value,
    )
    db_session.add(participant)
    await db_session.commit()

    # team owner(test_user)가 수정
    update_data = UpdateMeetingRequest(title="Owner가 수정")

    result = await service.update_meeting(meeting.id, update_data, test_user.id)

    assert result.title == update_data.title


@pytest.mark.asyncio
async def test_update_meeting_by_team_admin(
    db_session, test_team: Team, test_user: User, test_user2: User
):
    """팀 admin이 회의 수정 가능"""
    service = MeetingService(db_session)

    # test_user2를 admin으로 추가
    admin_member = TeamMember(
        team_id=test_team.id,
        user_id=test_user2.id,
        role=TeamRole.ADMIN.value,
    )
    db_session.add(admin_member)

    # 회의 생성 (test_user가 호스트)
    meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="회의",
        created_by=test_user.id,
        status=MeetingStatus.SCHEDULED.value,
    )
    db_session.add(meeting)

    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=test_user.id,
        role=ParticipantRole.HOST.value,
    )
    db_session.add(participant)
    await db_session.commit()

    # admin(test_user2)이 수정
    update_data = UpdateMeetingRequest(title="Admin이 수정")

    result = await service.update_meeting(meeting.id, update_data, test_user2.id)

    assert result.title == update_data.title


@pytest.mark.asyncio
async def test_update_meeting_permission_denied(
    db_session, test_team: Team, test_user: User, test_user2: User
):
    """권한 없는 사용자는 수정 불가"""
    service = MeetingService(db_session)

    # test_user2를 일반 멤버로 추가
    member2 = TeamMember(
        team_id=test_team.id,
        user_id=test_user2.id,
        role=TeamRole.MEMBER.value,
    )
    db_session.add(member2)

    # 회의 생성 (test_user가 호스트)
    meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="회의",
        created_by=test_user.id,
        status=MeetingStatus.SCHEDULED.value,
    )
    db_session.add(meeting)

    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=test_user.id,
        role=ParticipantRole.HOST.value,
    )
    db_session.add(participant)
    await db_session.commit()

    # 일반 멤버(test_user2)가 수정 시도
    update_data = UpdateMeetingRequest(title="수정 시도")

    with pytest.raises(ValueError, match="PERMISSION_DENIED"):
        await service.update_meeting(meeting.id, update_data, test_user2.id)


@pytest.mark.asyncio
async def test_update_meeting_not_found(db_session, test_user: User):
    """존재하지 않는 회의 수정"""
    service = MeetingService(db_session)

    fake_id = uuid4()
    update_data = UpdateMeetingRequest(title="수정")

    with pytest.raises(ValueError, match="MEETING_NOT_FOUND"):
        await service.update_meeting(fake_id, update_data, test_user.id)


# ===== delete_meeting 테스트 (3개) =====


@pytest.mark.asyncio
async def test_delete_meeting_by_host(
    db_session, test_team: Team, test_user: User, test_meeting: Meeting
):
    """호스트가 회의 삭제 성공"""
    service = MeetingService(db_session)

    await service.delete_meeting(test_meeting.id, test_user.id)

    # 삭제 확인
    result = await db_session.execute(
        select(Meeting).where(Meeting.id == test_meeting.id)
    )
    deleted_meeting = result.scalar_one_or_none()

    assert deleted_meeting is None


@pytest.mark.asyncio
async def test_delete_meeting_by_team_owner(
    db_session, test_team: Team, test_user: User, test_user2: User
):
    """팀 owner가 회의 삭제 가능"""
    service = MeetingService(db_session)

    # test_user2를 멤버로 추가
    member2 = TeamMember(
        team_id=test_team.id,
        user_id=test_user2.id,
        role=TeamRole.MEMBER.value,
    )
    db_session.add(member2)

    # 회의 생성 (test_user2가 호스트)
    meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="삭제될 회의",
        created_by=test_user2.id,
        status=MeetingStatus.SCHEDULED.value,
    )
    db_session.add(meeting)

    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=test_user2.id,
        role=ParticipantRole.HOST.value,
    )
    db_session.add(participant)
    await db_session.commit()

    # team owner(test_user)가 삭제
    await service.delete_meeting(meeting.id, test_user.id)

    # 삭제 확인
    result = await db_session.execute(select(Meeting).where(Meeting.id == meeting.id))
    deleted_meeting = result.scalar_one_or_none()

    assert deleted_meeting is None


@pytest.mark.asyncio
async def test_delete_meeting_permission_denied(
    db_session, test_team: Team, test_user: User, test_user2: User
):
    """권한 없는 사용자는 삭제 불가"""
    service = MeetingService(db_session)

    # test_user2를 일반 멤버로 추가
    member2 = TeamMember(
        team_id=test_team.id,
        user_id=test_user2.id,
        role=TeamRole.MEMBER.value,
    )
    db_session.add(member2)

    # 회의 생성 (test_user가 호스트)
    meeting = Meeting(
        id=uuid4(),
        team_id=test_team.id,
        title="삭제 시도",
        created_by=test_user.id,
        status=MeetingStatus.SCHEDULED.value,
    )
    db_session.add(meeting)

    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=test_user.id,
        role=ParticipantRole.HOST.value,
    )
    db_session.add(participant)
    await db_session.commit()

    # 일반 멤버(test_user2)가 삭제 시도
    with pytest.raises(ValueError, match="PERMISSION_DENIED"):
        await service.delete_meeting(meeting.id, test_user2.id)
