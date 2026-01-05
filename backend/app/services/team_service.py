import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team, TeamMember, TeamRole
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.team import (
    CreateTeamRequest,
    PaginationMeta,
    TeamListResponse,
    TeamMemberResponse,
    TeamResponse,
    TeamWithMembersResponse,
    UpdateTeamRequest,
)


class TeamService:
    """팀 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_team(self, data: CreateTeamRequest, user_id: UUID) -> TeamResponse:
        """팀 생성 (생성자는 자동으로 owner가 됨)"""
        # 팀 생성
        team = Team(
            name=data.name,
            description=data.description,
            created_by=user_id,
        )
        self.db.add(team)
        await self.db.flush()

        # 생성자를 owner로 추가
        member = TeamMember(
            team_id=team.id,
            user_id=user_id,
            role=TeamRole.OWNER.value,
        )
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(team)

        return TeamResponse.model_validate(team)

    async def list_my_teams(
        self, user_id: UUID, page: int = 1, limit: int = 20
    ) -> TeamListResponse:
        """내 팀 목록 조회"""
        # 내가 속한 팀 조회
        subquery = (
            select(TeamMember.team_id)
            .where(TeamMember.user_id == user_id)
            .scalar_subquery()
        )

        # 전체 개수 조회
        count_query = select(func.count()).select_from(Team).where(Team.id.in_(subquery))
        total = (await self.db.execute(count_query)).scalar() or 0

        # 페이지네이션
        offset = (page - 1) * limit
        query = (
            select(Team)
            .where(Team.id.in_(subquery))
            .order_by(Team.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        teams = result.scalars().all()

        return TeamListResponse(
            items=[TeamResponse.model_validate(team) for team in teams],
            meta=PaginationMeta(
                page=page,
                limit=limit,
                total=total,
                total_pages=math.ceil(total / limit) if total > 0 else 0,
            ),
        )

    async def get_team(self, team_id: UUID, user_id: UUID) -> TeamWithMembersResponse:
        """팀 상세 조회 (멤버 포함)"""
        # 팀 멤버인지 확인
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise ValueError("NOT_TEAM_MEMBER")

        # 팀 조회 (멤버 포함)
        query = (
            select(Team)
            .options(selectinload(Team.members).selectinload(TeamMember.user))
            .where(Team.id == team_id)
        )
        result = await self.db.execute(query)
        team = result.scalar_one_or_none()

        if not team:
            raise ValueError("TEAM_NOT_FOUND")

        # 응답 생성
        members_response = []
        for m in team.members:
            member_response = TeamMemberResponse(
                id=m.id,
                team_id=m.team_id,
                user_id=m.user_id,
                user=UserResponse.model_validate(m.user) if m.user else None,
                role=m.role,
                joined_at=m.joined_at,
            )
            members_response.append(member_response)

        return TeamWithMembersResponse(
            id=team.id,
            name=team.name,
            description=team.description,
            created_by=team.created_by,
            created_at=team.created_at,
            updated_at=team.updated_at,
            members=members_response,
        )

    async def update_team(
        self, team_id: UUID, data: UpdateTeamRequest, user_id: UUID
    ) -> TeamResponse:
        """팀 수정 (owner 또는 admin만 가능)"""
        # 권한 확인
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise ValueError("NOT_TEAM_MEMBER")
        if member.role not in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            raise ValueError("PERMISSION_DENIED")

        # 팀 조회
        query = select(Team).where(Team.id == team_id)
        result = await self.db.execute(query)
        team = result.scalar_one_or_none()

        if not team:
            raise ValueError("TEAM_NOT_FOUND")

        # 업데이트
        if data.name is not None:
            team.name = data.name
        if data.description is not None:
            team.description = data.description

        await self.db.flush()
        await self.db.refresh(team)

        return TeamResponse.model_validate(team)

    async def delete_team(self, team_id: UUID, user_id: UUID) -> None:
        """팀 삭제 (owner만 가능)"""
        # 권한 확인
        member = await self._get_team_member(team_id, user_id)
        if not member:
            raise ValueError("NOT_TEAM_MEMBER")
        if member.role != TeamRole.OWNER.value:
            raise ValueError("PERMISSION_DENIED")

        # 팀 조회
        query = select(Team).where(Team.id == team_id)
        result = await self.db.execute(query)
        team = result.scalar_one_or_none()

        if not team:
            raise ValueError("TEAM_NOT_FOUND")

        await self.db.delete(team)
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

    async def get_user_role_in_team(
        self, team_id: UUID, user_id: UUID
    ) -> str | None:
        """팀에서 사용자 역할 조회"""
        member = await self._get_team_member(team_id, user_id)
        return member.role if member else None
