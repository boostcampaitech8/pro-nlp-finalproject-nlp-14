"""LiveKit 웹훅 엔드포인트

LiveKit 서버에서 발생하는 이벤트를 처리합니다:
- 참여자 입장/퇴장 (participant_joined/left)
- 룸 생성/삭제 (room_started/ended)
"""

import logging
import time
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from livekit import api
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_arq_pool
from app.core.config import get_settings
from app.core.database import get_db
from app.core.neo4j_sync import neo4j_sync
from app.core.telemetry import get_mit_metrics
from app.infrastructure.worker_manager import get_worker_manager
from app.models.meeting import Meeting, MeetingStatus
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
    """
    # 서명 검증 및 이벤트 파싱
    body = await verify_and_parse_webhook(request, authorization)
    if body is None:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = body.get("event")
    logger.info(f"[LiveKit Webhook] Received event: {event_type}")

    # 이벤트별 처리
    if event_type == "participant_joined":
        await handle_participant_joined(body)
    elif event_type == "participant_left":
        await handle_participant_left(body)
    elif event_type == "room_started":
        await handle_room_started(body)
    elif event_type == "room_finished":
        await handle_room_finished(body, db)
    else:
        logger.debug(f"[LiveKit Webhook] Unhandled event type: {event_type}")

    return {"status": "ok"}


async def handle_room_started(body: dict) -> None:
    """룸 시작 이벤트 처리

    첫 번째 참여자가 입장하면 발생합니다.
    Realtime 워커를 시작합니다 (S2S 파이프라인: STT -> LLM -> TTS).
    """
    room = body.get("room", {})
    room_name = room.get("name", "")
    metrics = get_mit_metrics()

    logger.info(f"[LiveKit] Room started: {room_name}")

    # 회의 ID 추출 (room_name: "meeting-{uuid}")
    if room_name.startswith("meeting-"):
        meeting_id = room_name  # meeting-{uuid} 전체를 사용
        start_time = time.perf_counter()
        try:
            worker_manager = get_worker_manager()
            worker_id = await worker_manager.start_worker(meeting_id)

            # K8s Job 생성 시간 메트릭 기록
            duration = time.perf_counter() - start_time
            if metrics:
                metrics.webhook_to_job_latency.record(duration, {"meeting_id": meeting_id})
                metrics.realtime_worker_jobs_total.add(1, {"status": "created"})

            logger.info(
                f"[LiveKit] Realtime worker started: {worker_id}, duration={duration:.3f}s"
            )
        except Exception as e:
            if metrics:
                metrics.realtime_worker_jobs_total.add(1, {"status": "failed"})
            logger.error(f"[LiveKit] Failed to start realtime worker: {e}")


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

    happy path: Worker가 이미 /complete 호출 → COMPLETED 상태 → Job 삭제만 수행
    fallback: Worker 크래시 등으로 미완료 → 전체 완료 처리 + Job 삭제
    항상 수행: Clova API 키 반환, VAD 메타데이터 저장, Job 삭제
    """
    room = body.get("room", {})
    room_name = room.get("name", "")

    logger.info(f"[LiveKit] Room finished: {room_name}")

    # 회의 ID 추출
    if not room_name.startswith("meeting-"):
        return

    meeting_id = room_name  # meeting-{uuid} 전체를 사용
    meeting_id_str = room_name[8:]

    # Clova API 키 반환 (항상 실행)
    try:
        from app.services.clova_key_manager import get_clova_key_manager

        key_manager = await get_clova_key_manager()
        released = await key_manager.release_key(meeting_id)
        if released:
            logger.info(f"[LiveKit] Clova API key released: meeting={meeting_id}")
    except Exception as e:
        logger.error(f"[LiveKit] Failed to release Clova API key: {e}")

    # VAD 메타데이터 저장
    try:
        meeting_uuid = UUID(meeting_id_str)
        vad_metadata = await vad_event_service.store_meeting_vad_metadata(meeting_uuid)
        if vad_metadata:
            logger.info(
                f"[LiveKit] VAD metadata saved: meeting={meeting_uuid}, "
                f"users={len(vad_metadata)}"
            )
    except Exception as e:
        logger.error(f"[LiveKit] Failed to save VAD metadata: {e}")

    # Meeting 상태 확인 및 fallback 처리
    try:
        meeting_uuid = UUID(meeting_id_str)
        query = select(Meeting).where(Meeting.id == meeting_uuid)
        result = await db.execute(query)
        meeting = result.scalar_one_or_none()

        if not meeting:
            logger.warning(f"[LiveKit] Meeting not found: {meeting_uuid}")
        elif meeting.status == MeetingStatus.COMPLETED.value:
            # Happy path: Worker가 이미 처리함. Job 삭제만 수행.
            logger.info(f"[LiveKit] Meeting already completed (by worker): {meeting_uuid}")
        else:
            # Fallback: Worker가 완료하지 못함 (크래시 등)
            logger.warning(
                f"[LiveKit] Meeting NOT completed by worker, executing fallback: {meeting_uuid}"
            )
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

            # PR 큐잉 (Worker가 transcript 유무를 확인)
            try:
                pool = await get_arq_pool()
                await pool.enqueue_job(
                    "generate_pr_task",
                    str(meeting.id),
                    _job_id=f"generate_pr:{meeting.id}",
                )
                await pool.close()
                logger.info(
                    f"[LiveKit] PR generation task queued (fallback): meeting={meeting.id}"
                )
            except Exception as e:
                logger.error(f"[LiveKit] Failed to enqueue PR task (fallback): {e}")

    except Exception as e:
        logger.error(f"[LiveKit] Failed to process meeting (fallback): {e}")
        await db.rollback()

    # Job 삭제 (항상 실행 — happy path / fallback 공통)
    try:
        worker_manager = get_worker_manager()
        worker_id = f"realtime-worker-{meeting_id}"
        stopped = await worker_manager.stop_worker(worker_id)
        if stopped:
            logger.info(f"[LiveKit] Realtime worker job deleted: {worker_id}")
    except Exception as e:
        logger.error(f"[LiveKit] Failed to delete realtime worker job: {e}")
