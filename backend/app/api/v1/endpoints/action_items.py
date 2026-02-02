"""ActionItem API 엔드포인트

ActionItem 목록 조회/수정/삭제.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, handle_service_error
from app.core.neo4j import get_neo4j_driver
from app.models.user import User
from app.repositories.kg.repository import KGRepository
from app.schemas import ErrorResponse
from app.schemas.action_item import ActionItemResponse, UpdateActionItemRequest

router = APIRouter(prefix="/action-items", tags=["ActionItems"])


def get_kg_repo() -> KGRepository:
    driver = get_neo4j_driver()
    return KGRepository(driver)


@router.get(
    "",
    response_model=list[ActionItemResponse],
    summary="ActionItem 목록 조회",
    description="ActionItem 목록을 조회합니다. 담당자 또는 상태로 필터링할 수 있습니다.",
    responses={
        401: {"model": ErrorResponse},
    },
)
async def get_action_items(
    current_user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[KGRepository, Depends(get_kg_repo)],
    assignee_id: str | None = Query(default=None, alias="assigneeId"),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[ActionItemResponse]:
    items = await repo.get_action_items(user_id=assignee_id, status=status_filter)
    return [
        ActionItemResponse(
            id=item.id,
            title=item.title,
            description=item.description,
            status=item.status,
            assignee_id=item.assignee_id,
            due_date=item.due_date,
        )
        for item in items
    ]


@router.put(
    "/{action_item_id}",
    response_model=ActionItemResponse,
    summary="ActionItem 수정",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_action_item(
    action_item_id: str,
    request: UpdateActionItemRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[KGRepository, Depends(get_kg_repo)],
) -> ActionItemResponse:
    try:
        data = request.model_dump(exclude_none=True)
        item = await repo.update_action_item(action_item_id, str(current_user.id), data)
        return ActionItemResponse(
            id=item.id,
            title=item.title,
            description=item.description,
            status=item.status,
            assignee_id=item.assignee_id,
            due_date=item.due_date,
        )
    except ValueError as e:
        handle_service_error(e)


@router.delete(
    "/{action_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="ActionItem 삭제",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_action_item(
    action_item_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    repo: Annotated[KGRepository, Depends(get_kg_repo)],
) -> None:
    deleted = await repo.delete_action_item(action_item_id, str(current_user.id))
    if not deleted:
        handle_service_error(ValueError("ACTION_ITEM_NOT_FOUND"))
