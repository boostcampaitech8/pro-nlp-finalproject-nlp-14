"""Agent API 엔드포인트 (LLM 스트리밍)"""

import logging
import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import AGENT_USER_ID
from app.core.database import get_db
from app.infrastructure.agent import ClovaStudioLLMClient
from app.models.transcript import Transcript
from app.schemas.transcript import CreateTranscriptRequest
from app.services.agent_service import AgentService
from app.services.context_runtime import (
    get_or_create_runtime,
    get_transcript_start_ms,
    update_runtime_from_db,
)
from app.services.transcript_service import TranscriptService

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
    pre_transcript_id: UUID = Field(
        ..., alias="preTranscriptId", description="이전 transcript 기준 ID"
    )

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

    cutoff_start_ms = await get_transcript_start_ms(db, request.pre_transcript_id)
    if cutoff_start_ms is None:
        raise HTTPException(status_code=404, detail="Transcript not found")

    runtime = await get_or_create_runtime(str(request.meeting_id))
    async with runtime.lock:
        updated = await update_runtime_from_db(
            runtime,
            db,
            str(request.meeting_id),
            cutoff_start_ms,
        )
    logger.info(
        "Agent context update 완료: meeting_id=%s, added=%d",
        request.meeting_id,
        updated,
    )

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

    # 응답 저장용 변수
    full_response = ""
    is_completed = False
    response_start_time = datetime.now(timezone.utc)

    # 호출한 STT의 end_ms를 기준으로 타임스탬프 설정
    # STT 발화 직후부터 LLM 응답이 시작되는 것으로 처리
    response_start_ms = transcript.end_ms

    transcript_service = TranscriptService(db)

    async def event_generator():
        nonlocal full_response, is_completed

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
            full_response = response_text  # 응답 저장용 변수에 누적
            for line in response_text.splitlines():
                if line:  # 빈 줄 스킵
                    yield f"data: {line}\n\n"
            yield "data: [DONE]\n\n"
            is_completed = True  # 정상 완료 표시
        except Exception as e:
            logger.error("Agent Context 오류: %s", e, exc_info=True)
            yield f"data: [ERROR] {str(e)}\n\n"
        finally:
            # 응답이 있거나 인터럽트 시 저장
            if full_response.strip() or not is_completed:
                response_end_time = datetime.now(timezone.utc)
                # 응답 생성에 소요된 시간 계산
                elapsed_ms = int((response_end_time - response_start_time).total_seconds() * 1000)
                elapsed_ms = max(1, elapsed_ms)  # 최소 1ms 보장
                response_end_ms = response_start_ms + elapsed_ms

                # 빈 응답인 경우 플레이스홀더 텍스트 사용
                text_to_save = (
                    full_response.strip() if full_response.strip() else "[응답 생성 중 중단됨]"
                )

                try:
                    await transcript_service.create_transcript(
                        meeting_id=request.meeting_id,
                        request=CreateTranscriptRequest(
                            meeting_id=request.meeting_id,
                            user_id=AGENT_USER_ID,
                            start_ms=response_start_ms,
                            end_ms=response_end_ms,
                            text=text_to_save,
                            confidence=1.0,
                            min_confidence=1.0,
                            status="completed" if is_completed else "interrupted",
                        ),
                    )
                    await db.commit()
                    logger.info(
                        "Agent 응답 저장 완료: meeting_id=%s, status=%s, length=%d",
                        request.meeting_id,
                        "completed" if is_completed else "interrupted",
                        len(text_to_save),
                    )
                except Exception as save_error:
                    await db.rollback()
                    logger.error("Agent 응답 저장 실패: %s", save_error, exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
