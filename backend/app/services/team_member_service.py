from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team, TeamMember, TeamRole
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.team import TeamMemberResponse
from app.schemas.team_member import InviteTeamMemberRequest, UpdateTeamMemberRequest
from app.core.config import get_settings
from app.core.neo4j_sync import neo4j_sync


class TeamMemberService:
    """팀 멤버 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def invite_member(
        self,
        team_id: UUID,
        data: InviteTeamMemberRequest,
        current_user_id: UUID,
    ) -> TeamMemberResponse:
        """팀 멤버 초대 (owner 또는 admin만 가능)"""
        # 권한 확인
        current_member = await self._get_team_member(team_id, current_user_id)
        if not current_member:
            raise ValueError("NOT_TEAM_MEMBER")
        if current_member.role not in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            raise ValueError("PERMISSION_DENIED")

        # 팀원 수 제한 체크
        settings = get_settings()
        current_member_count = await self._count_members(team_id)
        if current_member_count >= settings.max_team_members:
            raise ValueError("TEAM_MEMBER_LIMIT_EXCEEDED")

        # 초대할 사용자 조회
        user = await self._get_user_by_email(data.email)
        if not user:
            raise ValueError("USER_NOT_FOUND")

        # 이미 팀 멤버인지 확인
        existing_member = await self._get_team_member(team_id, user.id)
        if existing_member:
            raise ValueError("ALREADY_MEMBER")

        # 역할 검증
        role = data.role.lower()
        if role not in [TeamRole.ADMIN.value, TeamRole.MEMBER.value]:
            role = TeamRole.MEMBER.value

        # 멤버 추가
        member = TeamMember(
            team_id=team_id,
            user_id=user.id,
            role=role,
        )
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)

        # Neo4j 동기화
        await neo4j_sync.sync_member_of_create(str(user.id), str(team_id), role)

        return TeamMemberResponse(
            id=member.id,
            team_id=member.team_id,
            user_id=member.user_id,
            user=UserResponse.model_validate(user),
            role=member.role,
            joined_at=member.joined_at,
        )

    async def list_members(
        self,
        team_id: UUID,
        current_user_id: UUID,
    ) -> list[TeamMemberResponse]:
        """팀 멤버 목록 조회"""
        # 팀 멤버인지 확인
        current_member = await self._get_team_member(team_id, current_user_id)
        if not current_member:
            raise ValueError("NOT_TEAM_MEMBER")

        # 멤버 목록 조회
        query = (
            select(TeamMember)
            .options(selectinload(TeamMember.user))
            .where(TeamMember.team_id == team_id)
            .order_by(TeamMember.joined_at)
        )
        result = await self.db.execute(query)
        members = result.scalars().all()

        return [
            TeamMemberResponse(
                id=m.id,
                team_id=m.team_id,
                user_id=m.user_id,
                user=UserResponse.model_validate(m.user) if m.user else None,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m in members
        ]

    async def update_member_role(
        self,
        team_id: UUID,
        user_id: UUID,
        data: UpdateTeamMemberRequest,
        current_user_id: UUID,
    ) -> TeamMemberResponse:
        """멤버 역할 수정 (owner만 가능)"""
        # 권한 확인 (owner만 가능)
        current_member = await self._get_team_member(team_id, current_user_id)
        if not current_member:
            raise ValueError("NOT_TEAM_MEMBER")
        if current_member.role != TeamRole.OWNER.value:
            raise ValueError("PERMISSION_DENIED")

        # 대상 멤버 조회
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise ValueError("MEMBER_NOT_FOUND")

        # owner 역할은 변경 불가
        if member.role == TeamRole.OWNER.value:
            raise ValueError("CANNOT_CHANGE_OWNER")

        # 역할 검증
        role = data.role.lower()
        if role not in [TeamRole.ADMIN.value, TeamRole.MEMBER.value]:
            raise ValueError("INVALID_ROLE")

        # 업데이트
        member.role = role
        await self.db.flush()

        # Neo4j 동기화
        await neo4j_sync.sync_member_of_update(str(user_id), str(team_id), role)

        # user 정보 로드
        user_query = select(User).where(User.id == user_id)
        user_result = await self.db.execute(user_query)
        user = user_result.scalar_one_or_none()

        return TeamMemberResponse(
            id=member.id,
            team_id=member.team_id,
            user_id=member.user_id,
            user=UserResponse.model_validate(user) if user else None,
            role=member.role,
            joined_at=member.joined_at,
        )

    async def remove_member(
        self,
        team_id: UUID,
        user_id: UUID,
        current_user_id: UUID,
    ) -> None:
        """멤버 제거"""
        # 현재 사용자 멤버십 확인
        current_member = await self._get_team_member(team_id, current_user_id)
        if not current_member:
            raise ValueError("NOT_TEAM_MEMBER")

        # 대상 멤버 조회
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise ValueError("MEMBER_NOT_FOUND")

        # 자기 자신을 제거하는 경우 항상 허용
        if user_id == current_user_id:
            # owner는 자신을 제거할 수 없음
            if member.role == TeamRole.OWNER.value:
                raise ValueError("OWNER_CANNOT_LEAVE")
            await self.db.delete(member)
            await self.db.flush()
            # Neo4j 동기화
            await neo4j_sync.sync_member_of_delete(str(user_id), str(team_id))
            return

        # 타인을 제거하는 경우 owner/admin만 가능
        if current_member.role not in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            raise ValueError("PERMISSION_DENIED")

        # admin은 다른 admin이나 owner를 제거할 수 없음
        if current_member.role == TeamRole.ADMIN.value:
            if member.role in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
                raise ValueError("PERMISSION_DENIED")

        # owner는 제거할 수 없음
        if member.role == TeamRole.OWNER.value:
            raise ValueError("CANNOT_REMOVE_OWNER")

        await self.db.delete(member)
        await self.db.flush()

        # Neo4j 동기화
        await neo4j_sync.sync_member_of_delete(str(user_id), str(team_id))

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

    async def _get_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _count_members(self, team_id: UUID) -> int:
        """팀 멤버 수 조회"""
        query = select(func.count(TeamMember.id)).where(
            TeamMember.team_id == team_id,
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
