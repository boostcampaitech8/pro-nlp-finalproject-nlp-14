"""LiveKit 웹훅 엔드포인트

LiveKit 서버에서 발생하는 이벤트를 처리합니다:
- 녹음 완료 (egress_ended)
- 참여자 입장/퇴장 (participant_joined/left)
- 룸 생성/삭제 (room_started/ended)
"""

import logging
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from livekit import api
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.recording import MeetingRecording, RecordingStatus
from app.services.livekit_service import livekit_service
from app.services.vad_event_service import vad_event_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/livekit", tags=["LiveKit Webhooks"])


async def verify_and_parse_webhook(
    request: Request,
    authorization: str = Header(None),
) -> dict[str, Any] | None:
    """LiveKit 웹훅 서명 검증 및 이벤트 파싱

    livekit-api의 WebhookReceiver를 사용하여 서명을 검증하고
    이벤트를 파싱합니다.

    Returns:
        검증된 이벤트 딕셔너리 또는 None (검증 실패 시)
    """
    settings = get_settings()

    if not authorization:
        logger.warning("[LiveKit Webhook] Missing Authorization header")
        return None

    if not settings.livekit_api_key or not settings.livekit_api_secret:
        logger.warning("[LiveKit Webhook] LiveKit not configured")
        return None

    try:
        body = await request.body()

        # TokenVerifier를 먼저 생성한 후 WebhookReceiver에 전달
        token_verifier = api.TokenVerifier(
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
        webhook_receiver = api.WebhookReceiver(token_verifier)

        # receive() 메서드가 서명 검증 + 이벤트 파싱 수행
        event = webhook_receiver.receive(body.decode(), authorization)

        if event is None:
            logger.warning("[LiveKit Webhook] Invalid webhook signature")
            return None

        # WebhookEvent를 dict로 변환 (MessageToDict 사용)
        from google.protobuf.json_format import MessageToDict

        # camelCase 필드명 사용 (egressInfo, roomName 등)
        return MessageToDict(event, preserving_proto_field_name=False)

    except Exception as e:
        logger.error(f"[LiveKit Webhook] Signature verification failed: {e}")
        return None


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
    # 서명 검증 및 이벤트 파싱
    body = await verify_and_parse_webhook(request, authorization)
    if body is None:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

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
    status = egress_info.get("status")  # EGRESS_COMPLETE, EGRESS_FAILED, EGRESS_ABORTED

    # 회의 ID 추출하여 활성 egress 캐시 정리 (모든 종료 상태에서 수행)
    if room_name.startswith("meeting-"):
        meeting_id_str = room_name[8:]
        try:
            meeting_id = UUID(meeting_id_str)
            await livekit_service.clear_active_egress(meeting_id)
        except ValueError:
            pass

    # 파일 정보 추출
    file_results = egress_info.get("fileResults", [])

    if status == "EGRESS_COMPLETE" and file_results:
        file_info = file_results[0]
        file_path = file_info.get("filename", "")
        # size와 duration은 문자열로 올 수 있음
        try:
            file_size = int(file_info.get("size", 0))
        except (ValueError, TypeError):
            file_size = 0
        # duration은 나노초 단위 (문자열로 올 수 있음), ms로 변환
        duration_ns = file_info.get("duration", 0)
        try:
            duration_ns = int(duration_ns) if duration_ns else 0
        except (ValueError, TypeError):
            duration_ns = 0
        duration_ms = duration_ns // 1_000_000 if duration_ns else 0

        logger.info(
            f"[LiveKit] Egress completed: room={room_name}, "
            f"file={file_path}, size={file_size}, duration={duration_ms}ms"
        )

        # 회의 ID 추출 (room_name: "meeting-{uuid}")
        if room_name.startswith("meeting-"):
            meeting_id_str = room_name[8:]  # "meeting-" 제거
            try:
                meeting_id = UUID(meeting_id_str)

                # Composite 녹음 레코드 생성 (user_id는 NULL)
                recording = MeetingRecording(
                    meeting_id=meeting_id,
                    user_id=None,  # Composite 녹음은 특정 사용자가 아님
                    file_path=file_path,
                    file_size_bytes=file_size,
                    duration_ms=duration_ms,
                    status=RecordingStatus.COMPLETED.value,
                    started_at=datetime.now(),  # Egress 시작 시간 (정확한 시간은 별도 저장 필요)
                    ended_at=datetime.now(),
                )
                db.add(recording)
                await db.commit()
                await db.refresh(recording)

                logger.info(
                    f"[LiveKit] Composite recording saved: meeting={meeting_id}, "
                    f"recording_id={recording.id}"
                )

                # TODO: STT 작업 큐잉 (필요시 활성화)
                # from app.workers.arq_worker import arq_redis
                # await arq_redis.enqueue_job("transcribe_recording_task", str(recording.id))

            except ValueError:
                logger.error(f"[LiveKit] Invalid meeting ID in room name: {room_name}")
            except Exception as e:
                logger.error(f"[LiveKit] Failed to save recording: {e}")
                await db.rollback()

    elif status == "EGRESS_FAILED":
        error = egress_info.get("error", "Unknown error")
        logger.error(f"[LiveKit] Egress failed: room={room_name}, error={error}")

    elif status == "EGRESS_ABORTED":
        error = egress_info.get("error", "Unknown error")
        logger.warning(f"[LiveKit] Egress aborted: room={room_name}, egress={egress_id}, error={error}")


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
