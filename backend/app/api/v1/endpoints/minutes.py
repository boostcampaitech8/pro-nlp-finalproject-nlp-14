"""Minutes API 엔드포인트

Meeting의 Minutes View 조회 (중첩 구조).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.minutes import MinutesResponse
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
