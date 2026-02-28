"""ActionItem 스키마"""

from datetime import datetime

from pydantic import BaseModel, Field


class UpdateActionItemRequest(BaseModel):
    """ActionItem 수정 요청"""

    content: str | None = None
    assignee_id: str | None = Field(default=None, serialization_alias="assigneeId")
    due_date: datetime | None = Field(default=None, serialization_alias="dueDate")
    status: str | None = None  # pending, in_progress, completed

    class Config:
        populate_by_name = True


class ActionItemResponse(BaseModel):
    """ActionItem 응답"""

    id: str
    content: str
    status: str
    assignee_id: str | None = Field(default=None, serialization_alias="assigneeId")
    due_date: datetime | None = Field(default=None, serialization_alias="dueDate")

    class Config:
        populate_by_name = True
