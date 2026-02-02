"""Context API - 실시간 토픽 피드"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_meeting_participant, require_meeting_participant_sse
from app.core.topic_pubsub import subscribe_topic_updates
from app.models.meeting import Meeting
from app.schemas.context import TopicFeedResponse, TopicItem
from app.services.context_runtime import get_or_create_runtime, update_runtime_from_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["Context"])


async def _build_topic_response(
    meeting_id: str, db: AsyncSession
) -> dict:
    """토픽 응답 데이터 생성 (재사용 가능한 헬퍼)"""
    runtime = await get_or_create_runtime(meeting_id)

    # DB 최신 발화를 런타임에 반영
    async with runtime.lock:
        await update_runtime_from_db(runtime, db, meeting_id, cutoff_start_ms=None)

    # 재입장 직후에도 기존 L1 토픽을 즉시 보여주기 위해 대기 중인 L1 처리 완료를 기다림
    if runtime.manager.has_pending_l1 or runtime.manager.is_l1_running:
        await runtime.manager.await_l1_idle()

    async with runtime.lock:
        manager = runtime.manager

        topics = [
            {
                "id": seg.id,
                "name": seg.name,
                "summary": seg.summary,
                "startTurn": seg.start_utterance_id,
                "endTurn": seg.end_utterance_id,
                "keywords": seg.keywords,
            }
            for seg in manager.l1_segments
        ]

        # 최신순 정렬 (endTurn 내림차순)
        topics.sort(key=lambda t: t["endTurn"], reverse=True)

        return {
            "meetingId": meeting_id,
            "pendingChunks": len(manager._pending_l1_chunks),
            "isL1Running": manager.is_l1_running,
            "currentTopic": manager.current_topic,
            "topics": topics,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }


@router.get(
    "/{meeting_id}/context/topics",
    response_model=TopicFeedResponse,
    response_model_by_alias=True,
    summary="실시간 L1 토픽 조회",
    responses={
        403: {"description": "회의 참여자가 아님"},
        404: {"description": "회의를 찾을 수 없음"},
    },
)
async def get_meeting_topics(
    meeting: Annotated[Meeting, Depends(require_meeting_participant)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopicFeedResponse:
    """회의의 실시간 L1 토픽을 조회합니다.

    토픽은 25발화 단위로 생성되며, 최신 토픽이 먼저 반환됩니다.

    **권장**: SSE 스트리밍 엔드포인트 `/context/topics/stream` 사용
    """
    meeting_id = str(meeting.id)

    runtime = await get_or_create_runtime(meeting_id)

    # 최신 발화 반영
    async with runtime.lock:
        await update_runtime_from_db(runtime, db, meeting_id, cutoff_start_ms=None)

    # snapshot API에서도 가능한 최신 L1 결과를 반환
    if runtime.manager.has_pending_l1 or runtime.manager.is_l1_running:
        await runtime.manager.await_l1_idle()

    async with runtime.lock:
        manager = runtime.manager

        topics = [
            TopicItem(
                id=seg.id,
                name=seg.name,
                summary=seg.summary,
                start_turn=seg.start_utterance_id,
                end_turn=seg.end_utterance_id,
                keywords=seg.keywords,
            )
            for seg in manager.l1_segments
        ]

        topics.sort(key=lambda t: t.end_turn, reverse=True)

        return TopicFeedResponse(
            meeting_id=meeting_id,
            pending_chunks=len(manager._pending_l1_chunks),
            is_l1_running=manager.is_l1_running,
            current_topic=manager.current_topic,
            topics=topics,
            updated_at=datetime.now(timezone.utc),
        )


@router.get(
    "/{meeting_id}/context/topics/stream",
    summary="실시간 L1 토픽 스트리밍 (SSE)",
    responses={
        403: {"description": "회의 참여자가 아님"},
        404: {"description": "회의를 찾을 수 없음"},
    },
)
async def stream_meeting_topics(
    request: Request,
    meeting: Annotated[Meeting, Depends(require_meeting_participant_sse)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """회의의 L1 토픽을 SSE로 스트리밍합니다.

    **이벤트 타입:**
    - `init`: 초기 토픽 데이터 (연결 직후)
    - `update`: 토픽 변경 시
    - `heartbeat`: 30초마다 keep-alive

    **사용 예시:**
    ```javascript
    const es = new EventSource('/api/v1/meetings/{id}/context/topics/stream');
    es.onmessage = (e) => console.log(JSON.parse(e.data));
    es.addEventListener('update', (e) => setTopics(JSON.parse(e.data)));
    ```
    """
    meeting_id = str(meeting.id)

    # DB 세션은 초기 데이터 조회에만 사용하고 즉시 반환
    # (SSE 스트림 동안 DB 커넥션 점유 방지)
    initial_data = await _build_topic_response(meeting_id, db)

    async def event_generator():
        try:
            # 1. 초기 데이터 전송
            yield f"event: init\ndata: {json.dumps(initial_data, ensure_ascii=False)}\n\n"

            # 2. Redis pub/sub 구독 (DB 불필요)
            async for message in subscribe_topic_updates(meeting_id):
                # 클라이언트 연결 확인
                if await request.is_disconnected():
                    logger.info("SSE 클라이언트 연결 끊김: meeting_id=%s", meeting_id)
                    break

                if message["type"] == "heartbeat":
                    yield ": heartbeat\n\n"
                elif message["type"] == "update":
                    data = json.dumps(message["data"], ensure_ascii=False)
                    yield f"event: update\ndata: {data}\n\n"

        except asyncio.CancelledError:
            logger.info("SSE 스트림 취소: meeting_id=%s", meeting_id)
        except Exception as e:
            logger.error("SSE 스트림 오류: meeting_id=%s, error=%s", meeting_id, e)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx buffering 비활성화
        },
    )
