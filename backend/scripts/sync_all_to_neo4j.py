#!/usr/bin/env python3
"""PostgreSQL -> Neo4j 전체 데이터 동기화 스크립트

기존 PostgreSQL 데이터를 Neo4j로 마이그레이션.
초기 동기화 또는 불일치 복구에 사용.

UNWIND 기반 배치 처리로 대량 데이터도 빠르게 동기화.

사용법:
    python scripts/sync_all_to_neo4j.py
    python scripts/sync_all_to_neo4j.py --clear  # Neo4j 초기화 후 동기화
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.neo4j import get_neo4j_driver
from app.models.meeting import Meeting, MeetingParticipant
from app.models.team import Team, TeamMember
from app.models.user import User
from app.repositories.kg.sync_repository import KGSyncRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def sync_all_to_neo4j(clear: bool = False):
    """PostgreSQL 전체 데이터를 Neo4j로 동기화 (배치 처리)"""
    driver = get_neo4j_driver()
    repo = KGSyncRepository(driver)

    logger.info("PostgreSQL -> Neo4j 동기화 시작 (배치 모드)")
    start_time = time.time()

    stats = {
        "users": 0,
        "teams": 0,
        "meetings": 0,
        "members": 0,
        "participants": 0,
    }

    async with async_session_maker() as db:
        if clear:
            logger.warning("Neo4j 동기화 데이터 초기화 중...")
            await repo.clear_sync_data()
            logger.info("Neo4j 동기화 데이터 초기화 완료")

        # 1. Users 동기화 (배치)
        logger.info("Users 동기화 시작...")
        result = await db.execute(select(User))
        users = result.scalars().all()
        user_data = [
            {"id": str(u.id), "name": u.name, "email": u.email} for u in users
        ]
        stats["users"] = await repo.batch_upsert_users(user_data)
        logger.info(f"Users 동기화 완료: {stats['users']}건")

        # 2. Teams 동기화 (배치)
        logger.info("Teams 동기화 시작...")
        result = await db.execute(select(Team))
        teams = result.scalars().all()
        team_data = [
            {"id": str(t.id), "name": t.name, "description": t.description}
            for t in teams
        ]
        stats["teams"] = await repo.batch_upsert_teams(team_data)
        logger.info(f"Teams 동기화 완료: {stats['teams']}건")

        # 3. Meetings 동기화 (배치, HOSTS 관계 포함)
        logger.info("Meetings 동기화 시작...")
        result = await db.execute(select(Meeting))
        meetings = result.scalars().all()
        meeting_data = [
            {
                "id": str(m.id),
                "team_id": str(m.team_id),
                "title": m.title,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in meetings
        ]
        stats["meetings"] = await repo.batch_upsert_meetings(meeting_data)
        logger.info(f"Meetings 동기화 완료: {stats['meetings']}건")

        # 4. TeamMembers (MEMBER_OF) 동기화 (배치)
        logger.info("TeamMembers (MEMBER_OF) 동기화 시작...")
        result = await db.execute(select(TeamMember))
        members = result.scalars().all()
        member_data = [
            {"user_id": str(m.user_id), "team_id": str(m.team_id), "role": m.role}
            for m in members
        ]
        stats["members"] = await repo.batch_upsert_member_of(member_data)
        logger.info(f"TeamMembers 동기화 완료: {stats['members']}건")

        # 5. MeetingParticipants (PARTICIPATED_IN) 동기화 (배치)
        logger.info("MeetingParticipants (PARTICIPATED_IN) 동기화 시작...")
        result = await db.execute(select(MeetingParticipant))
        participants = result.scalars().all()
        participant_data = [
            {"user_id": str(p.user_id), "meeting_id": str(p.meeting_id), "role": p.role}
            for p in participants
        ]
        stats["participants"] = await repo.batch_upsert_participated_in(participant_data)
        logger.info(f"MeetingParticipants 동기화 완료: {stats['participants']}건")

    await driver.close()

    elapsed = time.time() - start_time
    total = sum(stats.values())

    # 통계 출력
    logger.info("=" * 50)
    logger.info("동기화 완료!")
    logger.info(f"  - Users: {stats['users']}건")
    logger.info(f"  - Teams: {stats['teams']}건")
    logger.info(f"  - Meetings: {stats['meetings']}건")
    logger.info(f"  - TeamMembers (MEMBER_OF): {stats['members']}건")
    logger.info(f"  - MeetingParticipants (PARTICIPATED_IN): {stats['participants']}건")
    logger.info("-" * 50)
    logger.info(f"  총 {total}건 처리, 소요시간: {elapsed:.2f}초")
    if total > 0:
        logger.info(f"  처리속도: {total / elapsed:.1f}건/초")
    logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="PostgreSQL -> Neo4j 동기화",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
    python scripts/sync_all_to_neo4j.py          # 동기화 (기존 데이터 유지)
    python scripts/sync_all_to_neo4j.py --clear  # Neo4j 동기화 데이터 초기화 후 동기화
        """,
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Neo4j 동기화 대상 데이터 초기화 후 동기화 (GT 데이터는 유지)",
    )
    args = parser.parse_args()

    asyncio.run(sync_all_to_neo4j(clear=args.clear))


if __name__ == "__main__":
    main()
