from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import Meeting, MeetingParticipant, ParticipantRole
from app.models.team import TeamMember, TeamRole
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.meeting import MeetingParticipantResponse
from app.schemas.meeting_participant import (
    AddMeetingParticipantRequest,
    UpdateMeetingParticipantRequest,
)


class MeetingParticipantService:
    """회의 참여자 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_participant(
        self,
        meeting_id: UUID,
        data: AddMeetingParticipantRequest,
        current_user_id: UUID,
    ) -> MeetingParticipantResponse:
        """회의 참여자 추가 (host만 가능)"""
        # 회의 조회
        meeting = await self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 권한 확인 (host 또는 팀 owner/admin)
        has_permission = await self._check_permission(
            meeting_id, meeting.team_id, current_user_id
        )
        if not has_permission:
            raise ValueError("PERMISSION_DENIED")

        # 추가할 사용자가 팀 멤버인지 확인
        team_member = await self._get_team_member(meeting.team_id, data.user_id)
        if not team_member:
            raise ValueError("USER_NOT_TEAM_MEMBER")

        # 이미 참여자인지 확인
        existing = await self._get_participant(meeting_id, data.user_id)
        if existing:
            raise ValueError("ALREADY_PARTICIPANT")

        # 역할 검증
        role = data.role.lower()
        if role not in [ParticipantRole.HOST.value, ParticipantRole.PARTICIPANT.value]:
            role = ParticipantRole.PARTICIPANT.value

        # 참여자 추가
        participant = MeetingParticipant(
            meeting_id=meeting_id,
            user_id=data.user_id,
            role=role,
        )
        self.db.add(participant)
        await self.db.flush()
        await self.db.refresh(participant)

        # user 정보 로드
        user = await self._get_user(data.user_id)

        return MeetingParticipantResponse(
            id=participant.id,
            meeting_id=participant.meeting_id,
            user_id=participant.user_id,
            user=UserResponse.model_validate(user) if user else None,
            role=participant.role,
            joined_at=participant.joined_at,
        )

    async def list_participants(
        self,
        meeting_id: UUID,
        current_user_id: UUID,
    ) -> list[MeetingParticipantResponse]:
        """회의 참여자 목록 조회"""
        # 회의 조회
        meeting = await self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 팀 멤버인지 확인
        team_member = await self._get_team_member(meeting.team_id, current_user_id)
        if not team_member:
            raise ValueError("NOT_TEAM_MEMBER")

        # 참여자 목록 조회
        query = (
            select(MeetingParticipant)
            .options(selectinload(MeetingParticipant.user))
            .where(MeetingParticipant.meeting_id == meeting_id)
            .order_by(MeetingParticipant.joined_at)
        )
        result = await self.db.execute(query)
        participants = result.scalars().all()

        return [
            MeetingParticipantResponse(
                id=p.id,
                meeting_id=p.meeting_id,
                user_id=p.user_id,
                user=UserResponse.model_validate(p.user) if p.user else None,
                role=p.role,
                joined_at=p.joined_at,
            )
            for p in participants
        ]

    async def update_participant_role(
        self,
        meeting_id: UUID,
        user_id: UUID,
        data: UpdateMeetingParticipantRequest,
        current_user_id: UUID,
    ) -> MeetingParticipantResponse:
        """참여자 역할 수정 (host만 가능)"""
        # 회의 조회
        meeting = await self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 권한 확인
        has_permission = await self._check_permission(
            meeting_id, meeting.team_id, current_user_id
        )
        if not has_permission:
            raise ValueError("PERMISSION_DENIED")

        # 대상 참여자 조회
        participant = await self._get_participant(meeting_id, user_id)
        if not participant:
            raise ValueError("PARTICIPANT_NOT_FOUND")

        # 역할 검증
        role = data.role.lower()
        if role not in [ParticipantRole.HOST.value, ParticipantRole.PARTICIPANT.value]:
            raise ValueError("INVALID_ROLE")

        # 업데이트
        participant.role = role
        await self.db.flush()

        # user 정보 로드
        user = await self._get_user(user_id)

        return MeetingParticipantResponse(
            id=participant.id,
            meeting_id=participant.meeting_id,
            user_id=participant.user_id,
            user=UserResponse.model_validate(user) if user else None,
            role=participant.role,
            joined_at=participant.joined_at,
        )

    async def remove_participant(
        self,
        meeting_id: UUID,
        user_id: UUID,
        current_user_id: UUID,
    ) -> None:
        """참여자 제거"""
        # 회의 조회
        meeting = await self._get_meeting(meeting_id)
        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 대상 참여자 조회
        participant = await self._get_participant(meeting_id, user_id)
        if not participant:
            raise ValueError("PARTICIPANT_NOT_FOUND")

        # 자기 자신을 제거하는 경우 항상 허용
        if user_id == current_user_id:
            await self.db.delete(participant)
            await self.db.flush()
            return

        # 타인을 제거하는 경우 권한 확인
        has_permission = await self._check_permission(
            meeting_id, meeting.team_id, current_user_id
        )
        if not has_permission:
            raise ValueError("PERMISSION_DENIED")

        await self.db.delete(participant)
        await self.db.flush()

    async def _get_meeting(self, meeting_id: UUID) -> Meeting | None:
        """회의 조회"""
        query = select(Meeting).where(Meeting.id == meeting_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_participant(
        self, meeting_id: UUID, user_id: UUID
    ) -> MeetingParticipant | None:
        """회의 참여자 조회"""
        query = select(MeetingParticipant).where(
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.user_id == user_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

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

    async def _get_user(self, user_id: UUID) -> User | None:
        """사용자 조회"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _check_permission(
        self, meeting_id: UUID, team_id: UUID, user_id: UUID
    ) -> bool:
        """회의 수정 권한 확인 (host 또는 팀 owner/admin)"""
        # host인지 확인
        participant = await self._get_participant(meeting_id, user_id)
        if participant and participant.role == ParticipantRole.HOST.value:
            return True

        # 팀 owner/admin인지 확인
        member = await self._get_team_member(team_id, user_id)
        if member and member.role in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            return True

        return False
