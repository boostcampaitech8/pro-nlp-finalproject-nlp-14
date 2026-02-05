"""Spotlight 채팅 스키마"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SpotlightSessionCreate(BaseModel):
    """세션 생성 요청 (body 없음, 자동 생성)"""

    pass


class SpotlightSessionResponse(BaseModel):
    """세션 응답"""

    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class SpotlightSessionUpdate(BaseModel):
    """세션 수정 요청"""

    title: str


class SpotlightChatRequest(BaseModel):
    """채팅 요청

    Attributes:
        message: 사용자 메시지
        hitl_action: HITL 응답 (confirm: 실행 확인, cancel: 취소)
        hitl_params: HITL 확인 시 사용자가 입력한 파라미터
    """

    message: str
    hitl_action: Literal["confirm", "cancel"] | None = None
    hitl_params: dict | None = None


class HITLFieldOption(BaseModel):
    """HITL 필드 선택 옵션"""

    value: str  # 실제 저장될 값 (예: UUID)
    label: str  # 사용자에게 보여줄 텍스트 (예: 팀 이름)


class HITLRequiredField(BaseModel):
    """HITL 필수 입력 필드 정의"""

    name: str
    description: str
    type: str  # 'string' | 'uuid' | 'datetime' | 'number'
    required: bool
    # 새 필드: 입력 타입 및 옵션
    input_type: Literal["text", "select", "multiselect", "checkbox", "datetime", "number", "textarea"] = "text"
    options: list[HITLFieldOption] = []  # select/multiselect용 옵션
    placeholder: str | None = None  # 입력 힌트


class HITLData(BaseModel):
    """HITL 데이터"""

    tool_name: str
    params: dict = {}
    params_display: dict = {}  # UUID → 이름 변환된 표시용 값
    message: str = ""
    required_fields: list[HITLRequiredField] = []
    hitl_request_id: str | None = None


class DraftData(BaseModel):
    """스트리밍 중간 응답 (draft) 데이터"""

    request_id: str
    updated_at: datetime


class SpotlightMessageResponse(BaseModel):
    """메시지 히스토리 아이템"""

    role: str  # "user" | "assistant"
    content: str
    type: Literal["text", "hitl", "draft"] = "text"  # 메시지 타입
    hitl_status: Literal["pending", "confirmed", "cancelled"] | None = None
    hitl_data: HITLData | None = None
    draft_data: DraftData | None = None
