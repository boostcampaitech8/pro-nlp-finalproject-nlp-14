import json
import logging
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.neo4j_sync import neo4j_sync
from app.core.redis import get_redis
from app.models.team import Team, TeamMember, TeamRole
from app.schemas.invite_link import (
    AcceptInviteResponse,
    InviteLinkResponse,
    InvitePreviewResponse,
)

logger = logging.getLogger(__name__)

# Redis 키 프리픽스
INVITE_KEY_PREFIX = "invite:"
INVITE_TEAM_KEY_PREFIX = "invite:team:"
INVITE_LINK_TTL_SECONDS = 3600  # 초대 링크 유효 시간 (1시간)


class InviteLinkService:
    """초대 링크 서비스 (Redis 기반)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_invite_link(
        self,
        team_id: UUID,
        current_user_id: UUID,
    ) -> InviteLinkResponse:
        """초대 링크 생성 (owner/admin만 가능, 기존 링크 교체)"""
        # 권한 확인
        current_member = await self._get_team_member(team_id, current_user_id)
        if not current_member:
            raise ValueError("NOT_TEAM_MEMBER")
        if current_member.role not in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            raise ValueError("PERMISSION_DENIED")

        # 팀 존재 확인
        team = await self._get_team(team_id)
        if not team:
            raise ValueError("TEAM_NOT_FOUND")

        settings = get_settings()
        redis = await get_redis()
        ttl = INVITE_LINK_TTL_SECONDS

        # 기존 링크가 있으면 삭제
        team_key = f"{INVITE_TEAM_KEY_PREFIX}{team_id}"
        old_code = await redis.get(team_key)
        if old_code:
            await redis.delete(f"{INVITE_KEY_PREFIX}{old_code}")
            await redis.delete(team_key)

        # 새 코드 생성
        code = secrets.token_urlsafe(6)
        now = datetime.now(timezone.utc)
        invite_data = {
            "team_id": str(team_id),
            "created_by": str(current_user_id),
            "created_at": now.isoformat(),
        }

        # Redis에 저장 (TTL 적용)
        await redis.set(
            f"{INVITE_KEY_PREFIX}{code}",
            json.dumps(invite_data),
            ex=ttl,
        )
        await redis.set(team_key, code, ex=ttl)

        invite_url = f"{settings.frontend_base_url}/invite/{code}"
        expires_at = datetime.fromtimestamp(
            now.timestamp() + ttl, tz=timezone.utc
        )

        logger.info(f"[InviteLink] Generated invite link for team {team_id}")

        return InviteLinkResponse(
            code=code,
            invite_url=invite_url,
            team_id=team_id,
            created_by=current_user_id,
            created_at=now,
            expires_at=expires_at,
        )

    async def get_active_invite_link(
        self,
        team_id: UUID,
        current_user_id: UUID,
    ) -> InviteLinkResponse | None:
        """활성 초대 링크 조회 (팀 멤버만 가능)"""
        current_member = await self._get_team_member(team_id, current_user_id)
        if not current_member:
            raise ValueError("NOT_TEAM_MEMBER")

        redis = await get_redis()
        settings = get_settings()

        # 역방향 조회로 코드 찾기
        team_key = f"{INVITE_TEAM_KEY_PREFIX}{team_id}"
        code = await redis.get(team_key)
        if not code:
            return None

        # 코드로 상세 정보 조회
        invite_json = await redis.get(f"{INVITE_KEY_PREFIX}{code}")
        if not invite_json:
            # 역방향 키만 남아있는 경우 정리
            await redis.delete(team_key)
            return None

        invite_data = json.loads(invite_json)
        created_at = datetime.fromisoformat(invite_data["created_at"])

        # 남은 TTL로 만료 시간 계산
        remaining_ttl = await redis.ttl(f"{INVITE_KEY_PREFIX}{code}")
        if remaining_ttl <= 0:
            return None

        expires_at = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + remaining_ttl,
            tz=timezone.utc,
        )
        invite_url = f"{settings.frontend_base_url}/invite/{code}"

        return InviteLinkResponse(
            code=code,
            invite_url=invite_url,
            team_id=UUID(invite_data["team_id"]),
            created_by=UUID(invite_data["created_by"]),
            created_at=created_at,
            expires_at=expires_at,
        )

    async def deactivate_invite_link(
        self,
        team_id: UUID,
        current_user_id: UUID,
    ) -> None:
        """초대 링크 비활성화 (owner/admin만 가능)"""
        current_member = await self._get_team_member(team_id, current_user_id)
        if not current_member:
            raise ValueError("NOT_TEAM_MEMBER")
        if current_member.role not in [TeamRole.OWNER.value, TeamRole.ADMIN.value]:
            raise ValueError("PERMISSION_DENIED")

        redis = await get_redis()
        team_key = f"{INVITE_TEAM_KEY_PREFIX}{team_id}"
        code = await redis.get(team_key)

        if not code:
            raise ValueError("INVITE_NOT_FOUND")

        await redis.delete(f"{INVITE_KEY_PREFIX}{code}")
        await redis.delete(team_key)

        logger.info(f"[InviteLink] Deactivated invite link for team {team_id}")

    async def preview_invite(self, code: str) -> InvitePreviewResponse:
        """초대 링크 미리보기 (인증 불필요)"""
        redis = await get_redis()
        settings = get_settings()

        invite_json = await redis.get(f"{INVITE_KEY_PREFIX}{code}")
        if not invite_json:
            raise ValueError("INVITE_NOT_FOUND")

        invite_data = json.loads(invite_json)
        team_id = UUID(invite_data["team_id"])

        # 팀 정보 조회
        team = await self._get_team(team_id)
        if not team:
            raise ValueError("INVITE_NOT_FOUND")

        # 멤버 수 조회
        member_count = await self._count_members(team_id)

        return InvitePreviewResponse(
            team_name=team.name,
            team_description=team.description,
            member_count=member_count,
            max_members=settings.max_team_members,
        )

    async def accept_invite(
        self,
        code: str,
        current_user_id: UUID,
    ) -> AcceptInviteResponse:
        """초대 수락 (인증 필요, MEMBER 역할로 가입)"""
        redis = await get_redis()
        settings = get_settings()

        invite_json = await redis.get(f"{INVITE_KEY_PREFIX}{code}")
        if not invite_json:
            raise ValueError("INVITE_NOT_FOUND")

        invite_data = json.loads(invite_json)
        team_id = UUID(invite_data["team_id"])

        # 이미 멤버인지 확인
        existing_member = await self._get_team_member(team_id, current_user_id)
        if existing_member:
            raise ValueError("ALREADY_MEMBER")

        # 팀원 수 제한 체크
        current_count = await self._count_members(team_id)
        if current_count >= settings.max_team_members:
            raise ValueError("TEAM_MEMBER_LIMIT_EXCEEDED")

        # 멤버 추가 (항상 MEMBER 역할)
        member = TeamMember(
            team_id=team_id,
            user_id=current_user_id,
            role=TeamRole.MEMBER.value,
        )
        self.db.add(member)
        await self.db.flush()

        # Neo4j 동기화
        await neo4j_sync.sync_member_of_create(
            str(current_user_id), str(team_id), TeamRole.MEMBER.value
        )

        logger.info(
            f"[InviteLink] User {current_user_id} joined team {team_id} via invite link"
        )

        return AcceptInviteResponse(
            team_id=team_id,
            role=TeamRole.MEMBER.value,
        )

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

    async def _get_team(self, team_id: UUID) -> Team | None:
        """팀 조회"""
        query = select(Team).where(Team.id == team_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _count_members(self, team_id: UUID) -> int:
        """팀 멤버 수 조회"""
        query = select(func.count(TeamMember.id)).where(
            TeamMember.team_id == team_id,
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
