"""Agent API 엔드포인트 (LLM 스트리밍)"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.infrastructure.agent import ClovaStudioLLMClient
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentMeetingRequest(BaseModel):
    """Agent 실행 요청"""

    user_input: str = Field(..., description="STT 결과")


class AgentMeetingResponse(BaseModel):
    """Agent 실행 응답 (비스트리밍)"""

    response: str = Field(..., description="LLM 생성 응답")


def get_agent_service() -> AgentService:
    """AgentService 의존성"""
    settings = get_settings()

    llm_client = ClovaStudioLLMClient(
        api_key=settings.ncp_clovastudio_api_key,
        model="HCX-003",
        temperature=0.7,
        max_tokens=2048,
    )

    return AgentService(llm_client=llm_client)


@router.post(
    "/meeting",
    summary="Agent 실행 (스트리밍)",
    description="STT 결과를 입력으로 받아 LLM을 실행하고 스트리밍 응답을 반환합니다.",
)
async def run_agent_streaming(
    request: AgentMeetingRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
):
    logger.info("Agent 스트리밍 요청: user_input=%s...", request.user_input[:100])

    async def event_generator():
        try:
            async for token in agent_service.process_streaming(
                user_input=request.user_input,
            ):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Agent 스트리밍 오류: %s", e, exc_info=True)
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
