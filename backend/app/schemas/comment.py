"""Comment 스키마"""

from datetime import datetime

from pydantic import BaseModel, Field

from .common_brief import UserBriefResponse


class CreateCommentRequest(BaseModel):
    """Comment 생성 요청"""

    content: str


class CommentResponse(BaseModel):
    """Comment 응답 (대댓글 지원)"""

    id: str
    content: str
    author: UserBriefResponse
    replies: list["CommentResponse"] = []
    pending_agent_reply: bool = Field(
        default=False, serialization_alias="pendingAgentReply"
    )  # @mit 멘션 시 Agent 응답 대기 중
    is_error_response: bool = Field(
        default=False, serialization_alias="isErrorResponse"
    )  # AI 응답 생성 중 에러 발생 여부
    created_at: datetime = Field(serialization_alias="createdAt")

    class Config:
        populate_by_name = True


# Forward reference 해결
CommentResponse.model_rebuild()
