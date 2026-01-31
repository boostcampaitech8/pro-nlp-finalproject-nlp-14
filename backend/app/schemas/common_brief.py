"""Brief Response 스키마

Comment/Suggestion에서 사용되는 간략화된 응답 타입.
"""

from uuid import UUID

from pydantic import BaseModel


class UserBriefResponse(BaseModel):
    """사용자 간략 정보 (Comment/Suggestion 작성자 표시용)"""

    id: UUID
    name: str

    class Config:
        from_attributes = True


class DecisionBriefResponse(BaseModel):
    """Decision 간략 정보 (Suggestion이 생성한 Decision 표시용)"""

    id: str
    content: str
    status: str  # draft, latest, outdated

    class Config:
        from_attributes = True
