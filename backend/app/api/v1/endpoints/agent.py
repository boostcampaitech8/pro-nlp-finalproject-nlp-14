"""Agent API 엔드포인트 (LLM 스트리밍)"""

import logging
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.infrastructure.agent import ClovaStudioLLMClient
from app.models.transcript import Transcript
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])


def _strip_wake_word(text: str, wake_word: str) -> str:
    """문장 시작 부분의 wake word 패턴 제거

    예: "부덕아 오늘 회의 요약해줘" → "오늘 회의 요약해줘"
        "부덕이, 뭐하고 있어?" → "뭐하고 있어?"
        "부덕! 도와줘" → "도와줘"
    """
    if not wake_word or not text:
        return text

    # wake word + 호격/접미사 + 구두점/공백 패턴
    # 예: 부덕아, 부덕이, 부덕아!, 부덕, 등
    pattern = rf"^{re.escape(wake_word)}[아이]?[,!?\s]*"
    result = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    return result if result else text


class AgentMeetingCallRequest(BaseModel):
    """Agent Context Update 요청"""

    meeting_id: UUID = Field(..., alias="meetingId", description="회의 ID")
    pre_transcript_id: UUID = Field(..., alias="preTranscriptId", description="이전 transcript 기준 ID")

    model_config = {"populate_by_name": True}


class AgentMeetingRequest(BaseModel):
    """Agent 실행 요청"""

    meeting_id: UUID = Field(..., alias="meetingId", description="회의 ID")
    transcript_id: UUID = Field(..., alias="transcriptId", description="현재 발화 transcript ID")

    model_config = {"populate_by_name": True}


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
    "/meeting/call",
    summary="Agent Context Update",
    description="이전 transcript를 기준으로 context를 업데이트합니다.",
)
async def update_agent_context(
    request: AgentMeetingCallRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Agent context update -200만 반환"""
    logger.info(
        "Agent context update 요청: meeting_id=%s, pre_transcript_id=%s",
        request.meeting_id,
        request.pre_transcript_id,
    )

    # TODO: 이전 transcript 조회 후 context 저장 로직 구현
    # 1. pre_transcript_id의 created_at 조회
    # 2. 해당 시점 이전의 모든 transcript 조회
    # 3. meeting 테이블에 agent_context 저장

    return Response(status_code=200)


@router.post(
    "/meeting",
    summary="Agent 실행 (Context Engineering + Orchestration)",
    description="transcript ID를 기반으로 Context Engineering과 Orchestration Graph를 사용하여 응답을 생성합니다.",
)
async def run_agent_with_context(
    request: AgentMeetingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
):
    # transcriptId로 현재 발화 조회
    query = select(Transcript).where(Transcript.id == request.transcript_id)
    result = await db.execute(query)
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    settings = get_settings()
    raw_text = transcript.transcript_text
    user_input = _strip_wake_word(raw_text, settings.agent_wake_word)

    logger.info(
        "Agent Context 요청: meeting_id=%s, transcript_id=%s, raw='%s', cleaned='%s'",
        request.meeting_id,
        request.transcript_id,
        raw_text[:50] if raw_text else "",
        user_input[:50] if user_input else "",
    )

    async def event_generator():
        try:
            # Context Engineering + Orchestration Graph 사용
            response = await agent_service.process_with_context(
                user_input=user_input,
                meeting_id=str(request.meeting_id),
                user_id=str(transcript.user_id),
                db=db,
            )
            # SSE는 data 필드가 줄마다 분리되어야 하므로 줄 단위로 전송
            response_text = "" if response is None else str(response)
            for line in response_text.splitlines():
                if line:  # 빈 줄 스킵
                    yield f"data: {line}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Agent Context 오류: %s", e, exc_info=True)
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
