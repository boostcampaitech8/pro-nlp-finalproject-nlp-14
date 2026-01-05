"""WebRTC 시그널링 및 회의 제어 엔드포인트"""

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.core.webrtc_config import ICE_SERVERS, MAX_PARTICIPANTS, WSErrorCode
from app.models.meeting import Meeting, MeetingParticipant, MeetingStatus, ParticipantRole
from app.models.user import User
from app.schemas.webrtc import (
    EndMeetingResponse,
    IceServer,
    MeetingRoomResponse,
    RoomParticipant,
    SignalingMessageType,
    StartMeetingResponse,
)
from app.services.auth_service import AuthService
from app.services.signaling_service import connection_manager
from app.services.sfu_service import sfu_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["WebRTC"])


# ===== REST 엔드포인트 =====


@router.get("/{meeting_id}/room", response_model=MeetingRoomResponse)
async def get_meeting_room(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(AuthService.get_current_user)],
):
    """회의실 정보 조회"""
    # 회의 조회
    query = (
        select(Meeting)
        .options(selectinload(Meeting.participants).selectinload(MeetingParticipant.user))
        .where(Meeting.id == meeting_id)
    )
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "회의를 찾을 수 없습니다."})

    # 참여자인지 확인
    is_participant = any(p.user_id == current_user.id for p in meeting.participants)
    if not is_participant:
        raise HTTPException(status_code=403, detail={"error": "FORBIDDEN", "message": "회의 참여자만 접근할 수 있습니다."})

    # 현재 연결된 참여자 목록
    connected_participants = connection_manager.get_participants(meeting_id)

    return MeetingRoomResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        participants=connected_participants,
        ice_servers=[IceServer(**server) for server in ICE_SERVERS],
        max_participants=MAX_PARTICIPANTS,
    )


@router.post("/{meeting_id}/start", response_model=StartMeetingResponse)
async def start_meeting(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(AuthService.get_current_user)],
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

    # SFU 룸 생성
    sfu_service.get_or_create_room(meeting_id)

    return StartMeetingResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        started_at=meeting.started_at,
    )


@router.post("/{meeting_id}/end", response_model=EndMeetingResponse)
async def end_meeting(
    meeting_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(AuthService.get_current_user)],
):
    """회의 종료 (host만 가능)"""
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

    # 모든 WebSocket 연결 종료
    await connection_manager.close_all_connections(meeting_id, "회의가 종료되었습니다.")

    # SFU 룸 종료
    await sfu_service.close_room(meeting_id)

    return EndMeetingResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        ended_at=meeting.ended_at,
    )


# ===== WebSocket 엔드포인트 =====


@router.websocket("/{meeting_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    meeting_id: UUID,
    token: str = Query(...),
):
    """WebSocket 시그널링 엔드포인트"""
    # DB 세션 생성
    async for db in get_db():
        # 토큰 검증
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.close(code=WSErrorCode.INVALID_TOKEN, reason="Invalid token")
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=WSErrorCode.INVALID_TOKEN, reason="Invalid token")
            return

        user_uuid = UUID(user_id)

        # 사용자 조회
        user_result = await db.execute(select(User).where(User.id == user_uuid))
        user = user_result.scalar_one_or_none()
        if not user:
            await websocket.close(code=WSErrorCode.INVALID_TOKEN, reason="User not found")
            return

        # 회의 조회
        query = (
            select(Meeting)
            .options(selectinload(Meeting.participants))
            .where(Meeting.id == meeting_id)
        )
        result = await db.execute(query)
        meeting = result.scalar_one_or_none()

        if not meeting:
            await websocket.close(code=WSErrorCode.MEETING_NOT_FOUND, reason="Meeting not found")
            return

        # 회의 상태 확인
        if meeting.status != MeetingStatus.ONGOING.value:
            if meeting.status == MeetingStatus.SCHEDULED.value:
                await websocket.close(code=WSErrorCode.MEETING_NOT_STARTED, reason="Meeting not started")
            else:
                await websocket.close(code=WSErrorCode.MEETING_ALREADY_ENDED, reason="Meeting already ended")
            return

        # 참여자인지 확인
        participant = next((p for p in meeting.participants if p.user_id == user_uuid), None)
        if not participant:
            await websocket.close(code=WSErrorCode.NOT_PARTICIPANT, reason="Not a participant")
            return

        # 최대 참여자 수 확인
        current_count = connection_manager.get_connection_count(meeting_id)
        if current_count >= MAX_PARTICIPANTS:
            await websocket.close(code=WSErrorCode.ROOM_FULL, reason="Room is full")
            return

        # 연결 등록
        await connection_manager.connect(
            meeting_id=meeting_id,
            user_id=user_uuid,
            user_name=user.name,
            role=participant.role,
            websocket=websocket,
        )

        # SFU 피어 추가
        room = sfu_service.get_or_create_room(meeting_id)
        await room.add_peer(user_uuid)

        try:
            # 메시지 처리 루프
            await handle_websocket_messages(websocket, meeting_id, user_uuid)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: user={user_id}, meeting={meeting_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # 연결 해제
            await connection_manager.disconnect(meeting_id, user_uuid)
            await room.remove_peer(user_uuid)

            # 다른 참여자들에게 퇴장 알림
            await connection_manager.broadcast(
                meeting_id,
                {"type": SignalingMessageType.PARTICIPANT_LEFT, "userId": str(user_uuid)},
                exclude_user_id=user_uuid,
            )

        return


async def handle_websocket_messages(
    websocket: WebSocket,
    meeting_id: UUID,
    user_id: UUID,
) -> None:
    """WebSocket 메시지 처리"""
    while True:
        data = await websocket.receive_json()
        msg_type = data.get("type")

        if msg_type == SignalingMessageType.JOIN:
            await handle_join(meeting_id, user_id)

        elif msg_type == SignalingMessageType.OFFER:
            await handle_offer(meeting_id, user_id, data)

        elif msg_type == SignalingMessageType.ANSWER:
            await handle_answer(meeting_id, user_id, data)

        elif msg_type == SignalingMessageType.ICE_CANDIDATE:
            await handle_ice_candidate(meeting_id, user_id, data)

        elif msg_type == SignalingMessageType.LEAVE:
            break  # 루프 종료 -> finally에서 정리

        elif msg_type == SignalingMessageType.MUTE:
            await handle_mute(meeting_id, user_id, data)

        else:
            logger.warning(f"Unknown message type: {msg_type}")


async def handle_join(meeting_id: UUID, user_id: UUID) -> None:
    """join 메시지 처리"""
    # 현재 참여자 목록 전송
    participants = connection_manager.get_participants(meeting_id)
    participants_data = [
        {
            "userId": str(p.user_id),
            "userName": p.user_name,
            "role": p.role,
            "audioMuted": p.audio_muted,
        }
        for p in participants
    ]

    await connection_manager.send_to_user(
        meeting_id,
        user_id,
        {"type": SignalingMessageType.JOINED, "participants": participants_data},
    )

    # 다른 참여자들에게 새 참여자 알림
    current_participant = connection_manager.get_participant(meeting_id, user_id)
    if current_participant:
        await connection_manager.broadcast(
            meeting_id,
            {
                "type": SignalingMessageType.PARTICIPANT_JOINED,
                "participant": {
                    "userId": str(current_participant.user_id),
                    "userName": current_participant.user_name,
                    "role": current_participant.role,
                    "audioMuted": current_participant.audio_muted,
                },
            },
            exclude_user_id=user_id,
        )


async def handle_offer(meeting_id: UUID, user_id: UUID, data: dict) -> None:
    """offer 메시지 처리 (Mesh 모드: 타겟에게 전달)"""
    target_user_id = data.get("targetUserId")
    sdp = data.get("sdp")

    if not target_user_id or not sdp:
        return

    await connection_manager.send_to_user(
        meeting_id,
        UUID(target_user_id),
        {
            "type": SignalingMessageType.OFFER,
            "sdp": sdp,
            "fromUserId": str(user_id),
        },
    )


async def handle_answer(meeting_id: UUID, user_id: UUID, data: dict) -> None:
    """answer 메시지 처리 (Mesh 모드: 타겟에게 전달)"""
    target_user_id = data.get("targetUserId")
    sdp = data.get("sdp")

    if not target_user_id or not sdp:
        return

    await connection_manager.send_to_user(
        meeting_id,
        UUID(target_user_id),
        {
            "type": SignalingMessageType.ANSWER,
            "sdp": sdp,
            "fromUserId": str(user_id),
        },
    )


async def handle_ice_candidate(meeting_id: UUID, user_id: UUID, data: dict) -> None:
    """ice-candidate 메시지 처리"""
    target_user_id = data.get("targetUserId")
    candidate = data.get("candidate")

    if not candidate:
        return

    if target_user_id:
        # 특정 사용자에게 전송
        await connection_manager.send_to_user(
            meeting_id,
            UUID(target_user_id),
            {
                "type": SignalingMessageType.ICE_CANDIDATE,
                "candidate": candidate,
                "fromUserId": str(user_id),
            },
        )
    else:
        # 모든 사용자에게 전송
        await connection_manager.broadcast(
            meeting_id,
            {
                "type": SignalingMessageType.ICE_CANDIDATE,
                "candidate": candidate,
                "fromUserId": str(user_id),
            },
            exclude_user_id=user_id,
        )


async def handle_mute(meeting_id: UUID, user_id: UUID, data: dict) -> None:
    """mute 메시지 처리"""
    muted = data.get("muted", False)

    # 상태 업데이트
    connection_manager.update_mute_status(meeting_id, user_id, muted)

    # 다른 참여자들에게 알림
    await connection_manager.broadcast(
        meeting_id,
        {
            "type": SignalingMessageType.PARTICIPANT_MUTED,
            "userId": str(user_id),
            "muted": muted,
        },
        exclude_user_id=user_id,
    )
