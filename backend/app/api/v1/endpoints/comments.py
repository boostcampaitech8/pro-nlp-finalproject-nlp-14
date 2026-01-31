"""Comment API 엔드포인트

Decision에 대한 Comment/Reply CRUD.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.schemas import ErrorResponse
from app.schemas.comment import CommentResponse, CreateCommentRequest
from app.services.review_service import ReviewService

router = APIRouter(prefix="/comments", tags=["Comments"])

# decisions 하위 리소스 라우터
decisions_comments_router = APIRouter(prefix="/decisions", tags=["Decisions"])


def get_review_service() -> ReviewService:
    driver = get_neo4j_driver()
    return ReviewService(driver)


@decisions_comments_router.post(
    "/{decision_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Comment 생성",
    description="Decision에 Comment를 작성합니다. @mit 멘션 시 AI 에이전트가 자동 응답합니다.",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_comment(
    decision_id: str,
    request: CreateCommentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> CommentResponse:
    try:
        comment = await service.create_comment(
            decision_id=decision_id,
            user_id=str(current_user.id),
            content=request.content,
        )
        # Transform to response format
        return CommentResponse(
            id=comment.id,
            content=comment.content,
            author={"id": current_user.id, "name": current_user.name},
            replies=[],
            pending_agent_reply="@mit" in request.content.lower(),
            created_at=comment.created_at,
        )
    except ValueError as e:
        handle_service_error(e)


@router.post(
    "/{comment_id}/replies",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="대댓글 생성",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_reply(
    comment_id: str,
    request: CreateCommentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> CommentResponse:
    try:
        reply = await service.create_reply(
            comment_id=comment_id,
            user_id=str(current_user.id),
            content=request.content,
        )
        return CommentResponse(
            id=reply.id,
            content=reply.content,
            author={"id": current_user.id, "name": current_user.name},
            replies=[],
            pending_agent_reply="@mit" in request.content.lower(),
            created_at=reply.created_at,
        )
    except ValueError as e:
        handle_service_error(e)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Comment 삭제",
    description="Comment를 삭제합니다. 작성자만 삭제할 수 있습니다.",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_comment(
    comment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> None:
    deleted = await service.delete_comment(
        comment_id=comment_id,
        user_id=str(current_user.id),
    )
    if not deleted:
        handle_service_error(ValueError("COMMENT_NOT_FOUND"))
