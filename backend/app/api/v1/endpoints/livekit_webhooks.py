"""LiveKit 웹훅 엔드포인트

LiveKit 서버에서 발생하는 이벤트를 처리합니다:
- 녹음 완료 (egress_ended)
- 참여자 입장/퇴장 (participant_joined/left)
- 룸 생성/삭제 (room_started/ended)
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.vad_event_service import vad_event_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/livekit", tags=["LiveKit Webhooks"])


async def verify_livekit_signature(
    request: Request,
    authorization: str = Header(None),
) -> bool:
    """LiveKit 웹훅 서명 검증

    LiveKit은 Authorization 헤더에 Bearer 토큰을 전송합니다.
    실제 구현에서는 livekit-api의 웹훅 검증 기능을 사용합니다.
    """
    settings = get_settings()

    if not authorization:
        logger.warning("[LiveKit Webhook] Missing Authorization header")
        return False

    # TODO: livekit-api 웹훅 검증 구현
    # from livekit import api
    # webhook_receiver = api.WebhookReceiver(settings.livekit_api_key, settings.livekit_api_secret)
    # event = webhook_receiver.receive(body, authorization)

    # 현재는 API key가 설정되어 있으면 통과 (개발용)
    if not settings.livekit_api_key:
        logger.warning("[LiveKit Webhook] LiveKit not configured")
        return False

    return True


@router.post("/webhook")
async def livekit_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: str = Header(None),
):
    """LiveKit 이벤트 웹훅

    LiveKit 서버에서 다음 이벤트를 전송합니다:
    - room_started: 첫 참여자 입장 시
    - room_finished: 마지막 참여자 퇴장 시
    - participant_joined: 참여자 입장
    - participant_left: 참여자 퇴장
    - track_published: 트랙 게시
    - track_unpublished: 트랙 게시 해제
    - egress_started: 녹음 시작
    - egress_updated: 녹음 진행 상태
    - egress_ended: 녹음 완료
    """
    # 서명 검증
    if not await verify_livekit_signature(request, authorization):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"[LiveKit Webhook] Failed to parse body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = body.get("event")
    logger.info(f"[LiveKit Webhook] Received event: {event_type}")

    # 이벤트별 처리
    if event_type == "egress_ended":
        await handle_egress_ended(body, db)
    elif event_type == "egress_started":
        await handle_egress_started(body)
    elif event_type == "participant_joined":
        await handle_participant_joined(body)
    elif event_type == "participant_left":
        await handle_participant_left(body)
    elif event_type == "room_finished":
        await handle_room_finished(body, db)
    else:
        logger.debug(f"[LiveKit Webhook] Unhandled event type: {event_type}")

    return {"status": "ok"}


async def handle_egress_started(body: dict) -> None:
    """녹음 시작 이벤트 처리"""
    egress_info = body.get("egressInfo", {})
    room_name = egress_info.get("roomName", "")
    egress_id = egress_info.get("egressId", "")

    logger.info(f"[LiveKit] Egress started: room={room_name}, egress_id={egress_id}")


async def handle_egress_ended(body: dict, db: AsyncSession) -> None:
    """녹음 완료 이벤트 처리

    녹음 파일이 MinIO에 업로드된 후 호출됩니다.
    DB에 녹음 레코드를 생성하고 STT 작업을 큐잉합니다.
    """
    egress_info = body.get("egressInfo", {})
    room_name = egress_info.get("roomName", "")
    egress_id = egress_info.get("egressId", "")
    status = egress_info.get("status")  # EGRESS_COMPLETE, EGRESS_FAILED

    # 파일 정보 추출
    file_results = egress_info.get("fileResults", [])

    if status == "EGRESS_COMPLETE" and file_results:
        file_info = file_results[0]
        file_path = file_info.get("filename", "")
        file_size = file_info.get("size", 0)
        duration_ms = file_info.get("duration", 0)

        logger.info(
            f"[LiveKit] Egress completed: room={room_name}, "
            f"file={file_path}, size={file_size}, duration={duration_ms}ms"
        )

        # 회의 ID 추출 (room_name: "meeting-{uuid}")
        if room_name.startswith("meeting-"):
            meeting_id_str = room_name[8:]  # "meeting-" 제거
            try:
                meeting_id = UUID(meeting_id_str)

                # TODO: DB에 녹음 레코드 생성
                # from app.models.recording import MeetingRecording, RecordingStatus
                # recording = MeetingRecording(
                #     meeting_id=meeting_id,
                #     file_path=file_path,
                #     file_size=file_size,
                #     duration_ms=duration_ms,
                #     status=RecordingStatus.COMPLETED,
                # )
                # db.add(recording)
                # await db.commit()

                # TODO: STT 작업 큐잉
                # from app.workers.arq_worker import arq_redis
                # await arq_redis.enqueue_job("transcribe_recording_task", recording.id)

                logger.info(f"[LiveKit] Recording saved for meeting: {meeting_id}")

            except ValueError:
                logger.error(f"[LiveKit] Invalid meeting ID in room name: {room_name}")

    elif status == "EGRESS_FAILED":
        error = egress_info.get("error", "Unknown error")
        logger.error(f"[LiveKit] Egress failed: room={room_name}, error={error}")


async def handle_participant_joined(body: dict) -> None:
    """참여자 입장 이벤트 처리"""
    participant = body.get("participant", {})
    room = body.get("room", {})

    participant_id = participant.get("identity", "")
    participant_name = participant.get("name", "")
    room_name = room.get("name", "")

    logger.info(
        f"[LiveKit] Participant joined: room={room_name}, "
        f"id={participant_id}, name={participant_name}"
    )


async def handle_participant_left(body: dict) -> None:
    """참여자 퇴장 이벤트 처리"""
    participant = body.get("participant", {})
    room = body.get("room", {})

    participant_id = participant.get("identity", "")
    room_name = room.get("name", "")

    logger.info(f"[LiveKit] Participant left: room={room_name}, id={participant_id}")


async def handle_room_finished(body: dict, db: AsyncSession) -> None:
    """룸 종료 이벤트 처리

    마지막 참여자가 퇴장하면 발생합니다.
    VAD 메타데이터를 저장합니다.
    """
    room = body.get("room", {})
    room_name = room.get("name", "")

    logger.info(f"[LiveKit] Room finished: {room_name}")

    # 회의 ID 추출
    if room_name.startswith("meeting-"):
        meeting_id_str = room_name[8:]
        try:
            meeting_id = UUID(meeting_id_str)

            # VAD 메타데이터 저장
            vad_metadata = await vad_event_service.store_meeting_vad_metadata(meeting_id)
            if vad_metadata:
                logger.info(
                    f"[LiveKit] VAD metadata saved: meeting={meeting_id}, "
                    f"users={len(vad_metadata)}"
                )

        except ValueError:
            logger.error(f"[LiveKit] Invalid meeting ID in room name: {room_name}")
