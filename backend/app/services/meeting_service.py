import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, ParticipantRole
from app.models.team import TeamMember, TeamRole
from app.schemas.auth import UserResponse
from app.schemas.meeting import (
    CreateMeetingRequest,
    MeetingListResponse,
    MeetingParticipantResponse,
    MeetingResponse,
    MeetingWithParticipantsResponse,
    UpdateMeetingRequest,
)
from app.schemas.team import PaginationMeta


class MeetingService:
    """회의 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_meeting(
        self, team_id: UUID, data: CreateMeetingRequest, user_id: UUID
    ) -> MeetingResponse:
        """회의 생성 (팀 멤버만 가능, 생성자는 자동으로 host가 됨)"""
        # 팀 멤버인지 확인
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise ValueError("NOT_TEAM_MEMBER")

        # 회의 생성
        meeting = Meeting(
            team_id=team_id,
            title=data.title,
            description=data.description,
            scheduled_at=data.scheduled_at,
            created_by=user_id,
            status=MeetingStatus.SCHEDULED.value,
        )
        self.db.add(meeting)
        await self.db.flush()

        # 생성자를 host로 추가
        participant = MeetingParticipant(
            meeting_id=meeting.id,
            user_id=user_id,
            role=ParticipantRole.HOST.value,
        )
        self.db.add(participant)
        await self.db.flush()
        await self.db.refresh(meeting)

        return MeetingResponse.model_validate(meeting)

    async def list_team_meetings(
        self,
        team_id: UUID,
        user_id: UUID,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
    ) -> MeetingListResponse:
        """팀 회의 목록 조회"""
        # 팀 멤버인지 확인
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise ValueError("NOT_TEAM_MEMBER")

        # 기본 쿼리
        base_query = select(Meeting).where(Meeting.team_id == team_id)
        count_base = select(func.count()).select_from(Meeting).where(Meeting.team_id == team_id)

        # 상태 필터
        if status:
            base_query = base_query.where(Meeting.status == status)
            count_base = count_base.where(Meeting.status == status)

        # 전체 개수
        total = (await self.db.execute(count_base)).scalar() or 0

        # 페이지네이션
        offset = (page - 1) * limit
        query = base_query.order_by(Meeting.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        meetings = result.scalars().all()

        return MeetingListResponse(
            items=[MeetingResponse.model_validate(m) for m in meetings],
            meta=PaginationMeta(
                page=page,
                limit=limit,
                total=total,
                total_pages=math.ceil(total / limit) if total > 0 else 0,
            ),
        )

    async def get_meeting(
        self, meeting_id: UUID, user_id: UUID
    ) -> MeetingWithParticipantsResponse:
        """회의 상세 조회 (참여자 포함)"""
        # 회의 조회
        query = (
            select(Meeting)
            .options(selectinload(Meeting.participants).selectinload(MeetingParticipant.user))
            .where(Meeting.id == meeting_id)
        )
        result = await self.db.execute(query)
        meeting = result.scalar_one_or_none()

        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 팀 멤버인지 확인
        member = await self._get_team_member(meeting.team_id, user_id)
        if not member:
            raise ValueError("NOT_TEAM_MEMBER")

        # 응답 생성
        participants_response = []
        for p in meeting.participants:
            participant_response = MeetingParticipantResponse(
                id=p.id,
                meeting_id=p.meeting_id,
                user_id=p.user_id,
                user=UserResponse.model_validate(p.user) if p.user else None,
                role=p.role,
                joined_at=p.joined_at,
            )
            participants_response.append(participant_response)

        return MeetingWithParticipantsResponse(
            id=meeting.id,
            team_id=meeting.team_id,
            title=meeting.title,
            description=meeting.description,
            created_by=meeting.created_by,
            status=meeting.status,
            scheduled_at=meeting.scheduled_at,
            started_at=meeting.started_at,
            ended_at=meeting.ended_at,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            participants=participants_response,
        )

    async def update_meeting(
        self, meeting_id: UUID, data: UpdateMeetingRequest, user_id: UUID
    ) -> MeetingResponse:
        """회의 수정 (host 또는 팀 owner/admin만 가능)"""
        # 회의 조회
        query = select(Meeting).where(Meeting.id == meeting_id)
        result = await self.db.execute(query)
        meeting = result.scalar_one_or_none()

        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 권한 확인
        has_permission = await self._check_meeting_permission(
            meeting.id, meeting.team_id, user_id
        )
        if not has_permission:
            raise ValueError("PERMISSION_DENIED")

        # 업데이트
        if data.title is not None:
            meeting.title = data.title
        if data.description is not None:
            meeting.description = data.description
        if data.scheduled_at is not None:
            meeting.scheduled_at = data.scheduled_at
        if data.status is not None:
            meeting.status = data.status

        await self.db.flush()
        await self.db.refresh(meeting)

        return MeetingResponse.model_validate(meeting)

    async def delete_meeting(self, meeting_id: UUID, user_id: UUID) -> None:
        """회의 삭제 (host 또는 팀 owner/admin만 가능)"""
        # 회의 조회
        query = select(Meeting).where(Meeting.id == meeting_id)
        result = await self.db.execute(query)
        meeting = result.scalar_one_or_none()

        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 권한 확인
        has_permission = await self._check_meeting_permission(
            meeting.id, meeting.team_id, user_id
        )
        if not has_permission:
            raise ValueError("PERMISSION_DENIED")

        await self.db.delete(meeting)
        await self.db.flush()

    async def _get_team_member(
        self, team_id: UUID, user_id: UUID
    ) -> TeamMember | None:
        """팀 멤버 조회"""
        query = select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_meeting_participant(
        self, meeting_id: UUID, user_id: UUID
    ) -> MeetingParticipant | None:
        """회의 참여자 조회"""
        query = select(MeetingParticipant).where(
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.user_id == user_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _check_meeting_permission(
        self, meeting_id: UUID, team_id: UUID, user_id: UUID
    ) -> bool:
        """회의 수정/삭제 권한 확인 (host 또는 팀 owner/admin)"""
        # 회의 host인지 확인
        participant = await self._get_meeting_participant(meeting_id, user_id)
        if participant and participant.role == ParticipantRole.HOST.value:
            return True

        # 팀 owner/admin인지 확인
        member = await self._get_team_member(team_id, user_id)
        if member and member.role in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            return True

        return False
