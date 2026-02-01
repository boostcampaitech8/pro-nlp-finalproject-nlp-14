"""Suggestion API 엔드포인트

Decision에 대한 수정 제안.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.common_brief import DecisionBriefResponse, UserBriefResponse
from app.schemas.suggestion import CreateSuggestionRequest, SuggestionResponse
from app.services.review_service import ReviewService

# decisions 하위 리소스 라우터
decisions_suggestions_router = APIRouter(prefix="/decisions", tags=["Decisions"])


def get_review_service() -> ReviewService:
    driver = get_neo4j_driver()
    return ReviewService(driver)


@decisions_suggestions_router.post(
    "/{decision_id}/suggestions",
    response_model=SuggestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Suggestion 생성",
    description="Decision에 수정 제안을 작성합니다. 새로운 draft Decision이 함께 생성됩니다.",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_suggestion(
    decision_id: str,
    request: CreateSuggestionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> SuggestionResponse:
    try:
        suggestion = await service.create_suggestion(
            decision_id=decision_id,
            user_id=str(current_user.id),
            content=request.content,
            meeting_id=request.meeting_id,
        )
        return SuggestionResponse(
            id=suggestion.id,
            content=suggestion.content,
            author=UserBriefResponse(id=str(current_user.id), name=current_user.name),
            created_decision=DecisionBriefResponse(
                id=suggestion.created_decision_id,
                content=request.content,
                status="draft",
            )
            if suggestion.created_decision_id
            else None,
            created_at=suggestion.created_at,
        )
    except ValueError as e:
        handle_service_error(e)
