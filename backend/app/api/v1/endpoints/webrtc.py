"""LiveKit 기반 회의 제어 엔드포인트

LiveKit SFU를 사용한 실시간 음성 회의 기능:
- 회의 시작/종료
- LiveKit 토큰 발급
"""

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.neo4j_sync import neo4j_sync
from app.core.webrtc_config import MAX_PARTICIPANTS
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, ParticipantRole
from app.models.team import TeamMember
from app.models.user import User
from app.schemas.webrtc import (
    EndMeetingResponse,
    LiveKitRoomResponse,
    LiveKitTokenResponse,
    RoomParticipant,
    StartMeetingResponse,
)
from app.services.livekit_service import livekit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["WebRTC"])


# ===== 회의 제어 엔드포인트 =====


@router.post("/{meeting_id}/start", response_model=StartMeetingResponse)
async def start_meeting(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """회의 시작 (host만 가능)"""
    # 회의 조회
    query = (
        select(Meeting)
        .options(selectinload(Meeting.participants))
        .where(Meeting.id == meeting_id)
    )
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "회의를 찾을 수 없습니다."})

    # host인지 확인
    host_participant = next(
        (p for p in meeting.participants if p.user_id == current_user.id and p.role == ParticipantRole.HOST.value),
        None,
    )
    if not host_participant:
        raise HTTPException(status_code=403, detail={"error": "FORBIDDEN", "message": "host만 회의를 시작할 수 있습니다."})

    # 상태 확인
    if meeting.status == MeetingStatus.ONGOING.value:
        raise HTTPException(status_code=400, detail={"error": "BAD_REQUEST", "message": "이미 진행 중인 회의입니다."})
    if meeting.status in [MeetingStatus.COMPLETED.value, MeetingStatus.CANCELLED.value]:
        raise HTTPException(status_code=400, detail={"error": "BAD_REQUEST", "message": "이미 종료된 회의입니다."})

    # 회의 시작
    now = datetime.now(timezone.utc)
    meeting.status = MeetingStatus.ONGOING.value
    meeting.started_at = now
    await db.commit()
    await db.refresh(meeting)

    # LiveKit 룸 생성 (선택적 - 클라이언트 연결 시 자동 생성됨)
    if livekit_service.is_configured:
        room_name = livekit_service.get_room_name(meeting_id)
        await livekit_service.create_room(room_name, MAX_PARTICIPANTS)

    logger.info(f"Meeting {meeting_id} started by user {current_user.id}")

    return StartMeetingResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        started_at=meeting.started_at,
    )


@router.post("/{meeting_id}/end", response_model=EndMeetingResponse)
async def end_meeting(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """회의 종료 (host만 가능)

    회의 종료 시 자동으로 녹음을 중지하고 룸을 삭제합니다.
    """
    # 회의 조회
    query = (
        select(Meeting)
        .options(selectinload(Meeting.participants))
        .where(Meeting.id == meeting_id)
    )
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "회의를 찾을 수 없습니다."})

    # host인지 확인
    host_participant = next(
        (p for p in meeting.participants if p.user_id == current_user.id and p.role == ParticipantRole.HOST.value),
        None,
    )
    if not host_participant:
        raise HTTPException(status_code=403, detail={"error": "FORBIDDEN", "message": "host만 회의를 종료할 수 있습니다."})

    # 상태 확인
    if meeting.status != MeetingStatus.ONGOING.value:
        raise HTTPException(status_code=400, detail={"error": "BAD_REQUEST", "message": "진행 중인 회의가 아닙니다."})

    # 회의 종료
    now = datetime.now(timezone.utc)
    meeting.status = MeetingStatus.COMPLETED.value
    meeting.ended_at = now
    await db.commit()
    await db.refresh(meeting)

    # Neo4j 동기화
    await neo4j_sync.sync_meeting_update(
        str(meeting.id),
        str(meeting.team_id),
        meeting.title,
        meeting.status,
        meeting.created_at,
    )

    # LiveKit 룸 정리
    if livekit_service.is_configured:
        room_name = livekit_service.get_room_name(meeting_id)
        await livekit_service.delete_room(room_name)

    logger.info(f"Meeting {meeting_id} ended by user {current_user.id}")

    return EndMeetingResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        ended_at=meeting.ended_at,
    )


# ===== LiveKit 토큰 엔드포인트 =====


@router.post("/{meeting_id}/join-token", response_model=LiveKitTokenResponse)
async def get_livekit_join_token(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """LiveKit 룸 참여 토큰 발급

    토큰을 받은 클라이언트는 LiveKit SDK로 직접 연결합니다.
    """
    # LiveKit 설정 확인
    if not livekit_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail={"error": "SERVICE_UNAVAILABLE", "message": "LiveKit is not configured"},
        )

    # 회의 조회
    query = (
        select(Meeting)
        .options(selectinload(Meeting.participants))
        .where(Meeting.id == meeting_id)
    )
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "회의를 찾을 수 없습니다."},
        )

    # 회의 상태 확인
    if meeting.status != MeetingStatus.ONGOING.value:
        if meeting.status == MeetingStatus.SCHEDULED.value:
            raise HTTPException(
                status_code=400,
                detail={"error": "MEETING_NOT_STARTED", "message": "회의가 아직 시작되지 않았습니다."},
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": "MEETING_ENDED", "message": "이미 종료된 회의입니다."},
            )

    # 팀 멤버인지 확인
    member_query = select(TeamMember).where(
        TeamMember.team_id == meeting.team_id,
        TeamMember.user_id == current_user.id,
    )
    member_result = await db.execute(member_query)
    if not member_result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "message": "팀 멤버만 회의에 참여할 수 있습니다."},
        )

    # 역할 결정
    is_host = meeting.created_by == current_user.id

    # 룸 이름 생성
    room_name = livekit_service.get_room_name(meeting_id)

    # 토큰 생성
    token = livekit_service.generate_token(
        room_name=room_name,
        participant_id=str(current_user.id),
        participant_name=current_user.name,
        is_host=is_host,
    )

    logger.info(f"LiveKit token issued: user={current_user.id}, meeting={meeting_id}, host={is_host}")

    return LiveKitTokenResponse(
        token=token,
        ws_url=livekit_service.get_ws_url_for_client(),
        room_name=room_name,
    )


@router.get("/{meeting_id}/livekit-room", response_model=LiveKitRoomResponse)
async def get_livekit_room(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """LiveKit 룸 정보 조회 (토큰 포함)

    룸 정보와 참여 토큰을 한 번에 반환합니다.
    """
    # LiveKit 설정 확인
    if not livekit_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail={"error": "SERVICE_UNAVAILABLE", "message": "LiveKit is not configured"},
        )

    # 회의 조회
    query = (
        select(Meeting)
        .options(selectinload(Meeting.participants).selectinload(MeetingParticipant.user))
        .where(Meeting.id == meeting_id)
    )
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "회의를 찾을 수 없습니다."},
        )

    # 팀 멤버인지 확인
    member_query = select(TeamMember).where(
        TeamMember.team_id == meeting.team_id,
        TeamMember.user_id == current_user.id,
    )
    member_result = await db.execute(member_query)
    if not member_result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "message": "팀 멤버만 회의실에 접근할 수 있습니다."},
        )

    # 역할 결정
    is_host = meeting.created_by == current_user.id

    # 룸 이름 및 토큰 생성
    room_name = livekit_service.get_room_name(meeting_id)
    token = livekit_service.generate_token(
        room_name=room_name,
        participant_id=str(current_user.id),
        participant_name=current_user.name,
        is_host=is_host,
    )

    # LiveKit에서 현재 참여자 목록 조회
    lk_participants = await livekit_service.get_room_participants(room_name)

    # RoomParticipant 형식으로 변환
    participants = [
        RoomParticipant(
            user_id=UUID(p["id"]),
            user_name=p["name"],
            role=ParticipantRole.HOST.value if p["id"] == str(meeting.created_by) else ParticipantRole.PARTICIPANT.value,
            audio_muted=False,
        )
        for p in lk_participants
    ]

    return LiveKitRoomResponse(
        meeting_id=meeting.id,
        room_name=room_name,
        status=meeting.status,
        participants=participants,
        max_participants=MAX_PARTICIPANTS,
        ws_url=livekit_service.get_ws_url_for_client(),
        token=token,
    )
