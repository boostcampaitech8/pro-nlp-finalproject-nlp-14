"""
슬랙 테스트 팀 및 회의 생성 스크립트

본인 계정으로 "슬랙 테스트" 팀을 만들고, slack CSV 데이터로 회의를 생성합니다.

사용법:
    cd backend

    # 1. 팀 생성 (최초 1회)
    uv run python scripts/create_slack_test.py --create-team

    # 2. CSV로 회의 생성 및 PR 생성 (L1 토픽 포함)
    uv run python scripts/create_slack_test.py --csv ../slack/25.11.04.csv --title "25.11.04 회의"

    # 3. L1 토픽 없이 PR 생성
    uv run python scripts/create_slack_test.py --csv ../slack/25.11.04.csv --no-l1

    # 4. 모든 CSV 파일로 회의 생성
    uv run python scripts/create_slack_test.py --all

"""

import argparse
import asyncio
import csv
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.neo4j import get_neo4j_driver
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, ParticipantRole
from app.models.team import Team, TeamMember, TeamRole
from app.models.transcript import Transcript
from app.models.user import User
from app.infrastructure.context.manager import ContextManager
from app.infrastructure.context.models import Utterance
from app.repositories.kg.sync_repository import KGSyncRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 본인 계정 정보
MY_USER_ID = UUID("d8b37f27-28af-4803-b7ce-86966745f2af")
TEAM_NAME = "슬랙 테스트 v4"


def parse_csv_time(time_str: str) -> int:
    """CSV 시간 문자열을 밀리초로 변환"""
    parts = time_str.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = int(parts[0]), int(parts[1])
    else:
        return 0
    return (hours * 3600 + minutes * 60 + seconds) * 1000


def load_csv_data(csv_path: str) -> list[dict]:
    """CSV 파일 로드"""
    utterances = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            utterances.append({
                "user_name": row["USER_NAME"],
                "time_ms": parse_csv_time(row["TIME_STAMP"]),
                "text": row["CONTENTS"],
            })
    return utterances


async def sync_to_neo4j(
    user_id: UUID,
    user_name: str,
    user_email: str,
    team: Team,
    meeting: Meeting,
) -> None:
    """PostgreSQL 데이터를 Neo4j에 동기화

    실제 회의 흐름과 동일하게 Neo4j에도 데이터를 생성합니다:
    - User 노드
    - Team 노드 + MEMBER_OF 관계
    - Meeting 노드 + HOSTS 관계 + PARTICIPATED_IN 관계
    """
    try:
        driver = get_neo4j_driver()
        sync_repo = KGSyncRepository(driver)

        # 1. User 동기화
        await sync_repo.upsert_user(
            user_id=str(user_id),
            name=user_name,
            email=user_email,
        )
        logger.info(f"Neo4j User 동기화: {user_name}")

        # 2. Team 동기화
        await sync_repo.upsert_team(
            team_id=str(team.id),
            name=team.name,
            description=team.description,
        )
        logger.info(f"Neo4j Team 동기화: {team.name}")

        # 3. MEMBER_OF 관계 동기화
        await sync_repo.upsert_member_of(
            user_id=str(user_id),
            team_id=str(team.id),
            role=TeamRole.OWNER.value,
        )

        # 4. Meeting 동기화
        await sync_repo.upsert_meeting(
            meeting_id=str(meeting.id),
            team_id=str(team.id),
            title=meeting.title,
            status=meeting.status,
            created_at=meeting.created_at,
        )
        logger.info(f"Neo4j Meeting 동기화: {meeting.title}")

        # 5. PARTICIPATED_IN 관계 동기화
        await sync_repo.upsert_participated_in(
            user_id=str(user_id),
            meeting_id=str(meeting.id),
            role=ParticipantRole.HOST.value,
        )

        logger.info("Neo4j 동기화 완료!")

    except Exception as e:
        logger.warning(f"Neo4j 동기화 실패 (계속 진행): {e}")


async def get_or_create_team(session: AsyncSession) -> Team:
    """'슬랙 테스트' 팀 조회 또는 생성"""
    # 기존 팀 확인
    result = await session.execute(
        select(Team).where(Team.name == TEAM_NAME, Team.created_by == MY_USER_ID)
    )
    team = result.scalar_one_or_none()

    if team:
        logger.info(f"기존 팀 사용: '{team.name}' (ID: {team.id})")
        return team

    # 새 팀 생성
    team = Team(
        id=uuid4(),
        name=TEAM_NAME,
        description="슬랙 CSV 데이터 기반 PR 생성 테스트",
        created_by=MY_USER_ID,
    )
    session.add(team)
    await session.flush()

    # 팀 멤버 추가 (본인을 OWNER로)
    team_member = TeamMember(
        team_id=team.id,
        user_id=MY_USER_ID,
        role=TeamRole.OWNER.value,
    )
    session.add(team_member)
    await session.commit()

    logger.info(f"새 팀 생성: '{team.name}' (ID: {team.id})")
    return team


async def create_meeting_from_csv(
    session: AsyncSession,
    team: Team,
    csv_data: list[dict],
    meeting_title: str,
) -> Meeting:
    """CSV 데이터로 회의 및 트랜스크립트 생성"""

    # 회의 생성
    meeting = Meeting(
        id=uuid4(),
        team_id=team.id,
        title=meeting_title,
        description=f"슬랙 CSV 데이터 ({len(csv_data)}개 발화)",
        created_by=MY_USER_ID,
        status=MeetingStatus.COMPLETED.value,
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        ended_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    session.add(meeting)
    await session.flush()

    # 회의 참여자 추가 (본인을 HOST로)
    participant = MeetingParticipant(
        meeting_id=meeting.id,
        user_id=MY_USER_ID,
        role=ParticipantRole.HOST.value,
    )
    session.add(participant)
    await session.flush()

    logger.info(f"회의 생성: '{meeting.title}' (ID: {meeting.id})")

    # 트랜스크립트 생성 (모든 발화를 본인 계정으로)
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)
    for row in csv_data:
        start_ms = row["time_ms"]
        end_ms = start_ms + 3000

        # 발화 텍스트에 원래 화자 정보 포함
        text_with_speaker = f"[{row['user_name']}] {row['text']}"

        transcript = Transcript(
            id=uuid4(),
            meeting_id=meeting.id,
            user_id=MY_USER_ID,  # 본인 계정으로 저장
            start_ms=start_ms,
            end_ms=end_ms,
            start_at=base_time + timedelta(milliseconds=start_ms),
            transcript_text=text_with_speaker,
            confidence=0.95,
            min_confidence=0.90,
            agent_call=False,
            status="completed",
        )
        session.add(transcript)

    await session.commit()
    logger.info(f"트랜스크립트 {len(csv_data)}개 생성 완료")

    return meeting


async def generate_l1_topics(
    csv_data: list[dict],
    meeting_id: str,
) -> list[dict]:
    """CSV 데이터로 L1 토픽 생성

    ContextManager를 사용해서 발화를 추가하고 L1 토픽을 생성합니다.
    """
    logger.info("L1 토픽 생성 시작...")

    # ContextManager 생성
    manager = ContextManager(meeting_id=meeting_id)

    # CSV 데이터를 Utterance로 변환하고 추가
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)

    for i, row in enumerate(csv_data):
        utterance = Utterance(
            id=i + 1,
            speaker_id=str(MY_USER_ID),
            speaker_name=row["user_name"],
            text=row["text"],
            start_ms=row["time_ms"],
            end_ms=row["time_ms"] + 3000,
            confidence=0.95,
            absolute_timestamp=base_time + timedelta(milliseconds=row["time_ms"]),
        )
        await manager.add_utterance(utterance)

    # 대기 중인 L1 토픽 처리 완료
    await manager.await_pending_l1()

    # L1 토픽 스냅샷 생성
    l1_segments = manager.get_l1_segments()
    topics = [
        {
            "id": seg.id,
            "name": seg.name,
            "summary": seg.summary,
            "startTurn": seg.start_utterance_id,
            "endTurn": seg.end_utterance_id,
            "keywords": seg.keywords,
        }
        for seg in l1_segments
    ]

    logger.info(f"L1 토픽 {len(topics)}개 생성 완료")
    for topic in topics:
        logger.info(f"  - [{topic['startTurn']}-{topic['endTurn']}] {topic['name']}")

    return topics


def build_transcript_text(csv_data: list[dict]) -> str:
    """CSV 데이터를 트랜스크립트 텍스트로 변환"""
    lines = []
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)

    for row in csv_data:
        timestamp = base_time + timedelta(milliseconds=row["time_ms"])
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[{time_str}] [{row['user_name']}] {row['text']}")

    return "\n".join(lines)


def build_utterances(csv_data: list[dict]) -> list[dict]:
    """CSV 데이터를 utterances 형식으로 변환

    새 PR 생성 로직에서 필요한 발화 목록 형식:
    [{id, speaker_name, text, start_ms, end_ms}]
    """
    utterances = []
    for i, row in enumerate(csv_data):
        utterances.append({
            "id": str(i + 1),  # 1부터 시작하는 발화 ID
            "speaker_name": row["user_name"],
            "text": row["text"],
            "start_ms": row["time_ms"],
            "end_ms": row["time_ms"] + 3000,
        })
    return utterances


def normalize_generate_pr_utterances(utterances: list[dict]) -> list[dict]:
    """generate_pr 입력 스키마에 맞게 발화 목록을 정규화"""
    normalized: list[dict] = []
    for i, utterance in enumerate(utterances, start=1):
        start_ms = utterance.get("start_ms")
        end_ms = utterance.get("end_ms")

        normalized.append({
            "id": str(utterance.get("id") or i),
            "speaker_name": str(utterance.get("speaker_name") or "Unknown"),
            "text": str(utterance.get("text") or ""),
            "start_ms": int(start_ms) if start_ms is not None else None,
            "end_ms": int(end_ms) if end_ms is not None else None,
        })

    return normalized


async def run_generate_pr(
    meeting_id: str,
    transcript_text: str,
    utterances: list[dict],
    realtime_topics: list[dict] | None = None,
) -> dict:
    """PR 생성 워크플로우 직접 실행 (L1 토픽 → Agenda/Decision 추출 → Neo4j 저장)

    Args:
        meeting_id: 회의 ID
        transcript_text: 트랜스크립트 전문 텍스트
        utterances: 발화 목록 [{id, speaker_name, text, start_ms, end_ms}]
        realtime_topics: L1 토픽 목록 (선택)
    """
    from app.infrastructure.graph.workflows.generate_pr.graph import generate_pr_graph
    from app.infrastructure.graph.integration.langfuse import get_runnable_config

    normalized_utterances = normalize_generate_pr_utterances(utterances)
    logger.info(
        "PR 생성 워크플로우 시작... (발화: %d개, L1 토픽: %d개)",
        len(normalized_utterances),
        len(realtime_topics or []),
    )

    try:
        result = await generate_pr_graph.ainvoke(
            {
                "generate_pr_meeting_id": meeting_id,
                "generate_pr_transcript_text": transcript_text,
                "generate_pr_transcript_utterances": normalized_utterances,
                "generate_pr_realtime_topics": realtime_topics or [],
            },
            config=get_runnable_config(
                trace_name="generate_pr_script",
                metadata={"meeting_id": meeting_id},
            ),
        )

        agenda_ids = result.get("generate_pr_agenda_ids", [])
        decision_ids = result.get("generate_pr_decision_ids", [])
        summary = result.get("generate_pr_summary", "")
        agendas = result.get("generate_pr_agendas", [])

        logger.info(f"PR 생성 완료!")
        logger.info(f"  - Agenda: {len(agenda_ids)}개")
        logger.info(f"  - Decision: {len(decision_ids)}개")

        if agendas:
            logger.info(f"\n생성된 Agenda 목록:")
            for agenda in agendas:
                topic = agenda.get("topic", "N/A")
                desc = agenda.get("description", "")[:50]
                decision = agenda.get("decision")
                decision_text = decision.get("content", "")[:50] if decision else "없음"
                logger.info(f"  - {topic}")
                logger.info(f"    설명: {desc}...")
                logger.info(f"    결정: {decision_text}")

        if summary:
            logger.info(f"\n회의 요약:")
            logger.info(f"  {summary}")

        return {
            "status": "success",
            "meeting_id": meeting_id,
            "agenda_count": len(agenda_ids),
            "decision_count": len(decision_ids),
            "summary": summary,
            "agendas": agendas,
        }

    except Exception as e:
        logger.exception(f"PR 생성 실패: {e}")
        return {
            "status": "failed",
            "meeting_id": meeting_id,
            "error": str(e),
        }


async def main():
    parser = argparse.ArgumentParser(description="슬랙 테스트 팀 및 회의 생성")
    parser.add_argument("--create-team", action="store_true", help="팀만 생성")
    parser.add_argument("--csv", help="CSV 파일 경로")
    parser.add_argument("--title", default="슬랙 회의", help="회의 제목")
    parser.add_argument("--all", action="store_true", help="모든 CSV 파일 처리")
    parser.add_argument("--no-pr", action="store_true", help="PR 생성 건너뛰기")
    parser.add_argument("--no-l1", action="store_true", help="L1 토픽 생성 건너뛰기")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        # 사용자 정보 조회 (Neo4j 동기화용)
        user_result = await session.execute(select(User).where(User.id == MY_USER_ID))
        user = user_result.scalar_one_or_none()
        if not user:
            logger.error(f"사용자를 찾을 수 없습니다: {MY_USER_ID}")
            await engine.dispose()
            return

        # 팀 생성/조회
        team = await get_or_create_team(session)

        if args.create_team:
            # 팀도 Neo4j에 동기화
            try:
                driver = get_neo4j_driver()
                sync_repo = KGSyncRepository(driver)
                await sync_repo.upsert_user(str(user.id), user.name, user.email)
                await sync_repo.upsert_team(str(team.id), team.name, team.description)
                await sync_repo.upsert_member_of(str(user.id), str(team.id), TeamRole.OWNER.value)
                logger.info("Neo4j 팀 동기화 완료!")
            except Exception as e:
                logger.warning(f"Neo4j 동기화 실패: {e}")
            logger.info("팀 생성 완료!")
            await engine.dispose()
            return

        # CSV 파일 처리
        csv_files = []
        if args.all:
            slack_dir = Path(__file__).parent.parent.parent / "slack"
            csv_files = sorted(slack_dir.glob("*.csv"))
        elif args.csv:
            csv_files = [Path(args.csv)]

        if not csv_files:
            logger.error("처리할 CSV 파일이 없습니다. --csv 또는 --all 옵션을 사용하세요.")
            await engine.dispose()
            return

        for csv_path in csv_files:
            logger.info(f"\n{'='*60}")
            logger.info(f"처리 중: {csv_path.name}")
            logger.info(f"{'='*60}")

            # CSV 로드
            csv_data = load_csv_data(str(csv_path))
            logger.info(f"발화 수: {len(csv_data)}")

            # 회의 제목 생성
            if args.all:
                title = csv_path.stem  # 파일명에서 확장자 제거
            else:
                title = args.title

            # 회의 생성
            meeting = await create_meeting_from_csv(session, team, csv_data, title)

            # Neo4j 동기화 (실제 환경과 동일하게)
            await sync_to_neo4j(
                user_id=user.id,
                user_name=user.name,
                user_email=user.email,
                team=team,
                meeting=meeting,
            )

            # L1 토픽 생성 (선택적)
            l1_topics = None
            if not args.no_l1:
                l1_topics = await generate_l1_topics(csv_data, str(meeting.id))

            # PR 생성 (워크플로우 직접 실행)
            if not args.no_pr:
                transcript_text = build_transcript_text(csv_data)
                utterances = build_utterances(csv_data)
                result = await run_generate_pr(
                    meeting_id=str(meeting.id),
                    transcript_text=transcript_text,
                    utterances=utterances,
                    realtime_topics=l1_topics,
                )

                if result["status"] == "success":
                    logger.info(f"PR 생성 성공: Agenda {result['agenda_count']}개, Decision {result['decision_count']}개")

                else:
                    logger.error(f"PR 생성 실패: {result.get('error', 'Unknown error')}")

            logger.info(f"완료: {title}")

    await engine.dispose()
    logger.info("\n모든 작업 완료!")


if __name__ == "__main__":
    asyncio.run(main())
