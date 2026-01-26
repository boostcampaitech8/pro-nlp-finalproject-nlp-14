"""Decision 리뷰 API 엔드포인트

RESTful 설계: Review를 리소스로 모델링 (GitHub PR Review 스타일)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.review import (
    DecisionListResponse,
    DecisionResponse,
    DecisionReviewRequest,
    DecisionReviewResponse,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/decisions", tags=["Decisions"])


def get_review_service() -> ReviewService:
    """ReviewService 의존성"""
    driver = get_neo4j_driver()
    return ReviewService(driver)


@router.post(
    "/{decision_id}/reviews",
    response_model=DecisionReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="리뷰 생성 (승인/거절)",
    description="결정에 대한 리뷰를 생성합니다. 모든 참여자가 approve하면 자동 머지됩니다.",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_decision_review(
    decision_id: str,
    request: DecisionReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> DecisionReviewResponse:
    """리뷰 생성 (approve 또는 reject)"""
    try:
        return await service.create_review(
            decision_id=decision_id,
            user_id=str(current_user.id),
            action=request.action,
        )
    except ValueError as e:
        handle_service_error(e)


@router.get(
    "/{decision_id}",
    response_model=DecisionResponse,
    summary="결정 상세 조회",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_decision(
    decision_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> DecisionResponse:
    """결정사항 상세 조회"""
    try:
        return await service.get_decision(decision_id)
    except ValueError as e:
        handle_service_error(e)


# meetings 하위 리소스 라우터
meetings_decisions_router = APIRouter(prefix="/meetings", tags=["Meetings"])


@meetings_decisions_router.get(
    "/{meeting_id}/decisions",
    response_model=DecisionListResponse,
    summary="회의의 결정 목록 조회",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_meeting_decisions(
    meeting_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> DecisionListResponse:
    """회의에 속한 모든 결정사항 목록 조회"""
    try:
        return await service.get_meeting_decisions(meeting_id)
    except ValueError as e:
        handle_service_error(e)
