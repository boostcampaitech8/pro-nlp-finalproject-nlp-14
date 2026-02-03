"""Minutes API 엔드포인트

Meeting의 Minutes View 조회 (중첩 구조).
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.minutes import MinutesResponse
from app.services.minutes_events import minutes_event_manager
from app.services.minutes_service import MinutesService

# meetings 하위 리소스 라우터
meetings_minutes_router = APIRouter(prefix="/meetings", tags=["Meetings"])


def get_minutes_service() -> MinutesService:
    driver = get_neo4j_driver()
    return MinutesService(driver)


@meetings_minutes_router.get(
    "/{meeting_id}/minutes",
    response_model=MinutesResponse,
    summary="Minutes View 조회",
    description="회의록 전체 View를 중첩 구조로 조회합니다. (Agenda → Decision → Suggestion/Comment)",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_minutes(
    meeting_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MinutesService, Depends(get_minutes_service)],
) -> MinutesResponse:
    try:
        return await service.get_minutes(meeting_id)
    except ValueError as e:
        handle_service_error(e)


@meetings_minutes_router.get(
    "/{meeting_id}/minutes/events",
    summary="Minutes 이벤트 스트림 (SSE)",
    description="회의록 변경 이벤트를 실시간으로 수신합니다.",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def minutes_events(meeting_id: str) -> StreamingResponse:
    """Minutes 이벤트 스트림 (실시간 협업용)

    인증 없음 - SSE가 반환하는 건 이벤트 알림뿐 (민감정보 없음)
    실제 데이터는 별도 API (인증됨)로만 조회 가능
    meeting_id는 UUID이므로 추측 불가

    이벤트 타입:
    - comment_created: 댓글 생성
    - comment_reply_ready: AI 응답 완료
    - comment_deleted: 댓글 삭제
    - suggestion_created: 제안 생성
    - decision_updated: 결정 수정
    - decision_review_changed: 승인/거절
    - keepalive: 연결 유지 (30초 간격)

    Args:
        meeting_id: 구독할 회의 ID

    Returns:
        StreamingResponse: Server-Sent Events 스트림
    """

    async def event_generator():
        async for event in minutes_event_manager.subscribe(meeting_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx buffering 방지
        },
    )
