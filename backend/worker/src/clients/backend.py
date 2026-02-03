"""Backend API 클라이언트"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import httpx
import json

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegmentRequest:
    """트랜스크립트 세그먼트 요청"""

    meeting_id: str
    user_id: str
    start_ms: int
    end_ms: int
    text: str
    confidence: float
    min_confidence: float = 0.0
    agent_call: bool = False
    agent_call_keyword: str | None = None
    agent_call_confidence: float | None = None


@dataclass
class TranscriptSegmentResponse:
    """트랜스크립트 세그먼트 응답"""

    id: str
    created_at: datetime


class BackendAPIClient:
    """Backend API 클라이언트

    Realtime Worker ↔ Backend 통신:
    - STT 결과 전송 (현재)
    - RAG 응답 수신 (향후)
    """

    def __init__(self):
        self.config = get_config()
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """HTTP 클라이언트 초기화"""
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(
            base_url=self.config.backend_api_url,
            timeout=httpx.Timeout(30.0),
            headers={
                "Content-Type": "application/json",
                "X-Worker-Key": self.config.backend_api_key,
            },
        )
        logger.info(f"Backend API 클라이언트 연결: {self.config.backend_api_url}")

    async def disconnect(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Backend API 클라이언트 종료")

    async def send_transcript_segment(
        self,
        segment: TranscriptSegmentRequest,
    ) -> TranscriptSegmentResponse | None:
        """트랜스크립트 세그먼트 전송

        Args:
            segment: 트랜스크립트 세그먼트 데이터

        Returns:
            저장된 세그먼트 정보 또는 None (실패 시)
        """
        if self._client is None:
            await self.connect()

        if self._client is None:
            raise RuntimeError("HTTP 클라이언트가 초기화되지 않음")

        try:
            # meeting_id에서 "meeting-" 접두사 제거 (순수 UUID만 사용)
            pure_meeting_id = segment.meeting_id.replace("meeting-", "")
            pure_user_id = segment.user_id.replace("user-", "")

            payload = {
                "meetingId": pure_meeting_id,
                "userId": pure_user_id,
                "startMs": segment.start_ms,
                "endMs": segment.end_ms,
                "text": segment.text,
                "confidence": segment.confidence,
                "minConfidence": segment.min_confidence,
            }

            if segment.agent_call:
                payload["agentCall"] = segment.agent_call

            if segment.agent_call_keyword is not None:
                payload["agentCallKeyword"] = segment.agent_call_keyword

            if segment.agent_call_confidence is not None:
                payload["agentCallConfidence"] = segment.agent_call_confidence

            response = await self._client.post(
                f"/api/v1/meetings/{pure_meeting_id}/transcripts",
                json=payload,
            )

            if response.status_code == 201:
                data = response.json()
                return TranscriptSegmentResponse(
                    id=data["id"],
                    created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
                )
            else:
                logger.error(
                    f"트랜스크립트 전송 실패: {response.status_code} - {response.text}"
                )
                return None

        except httpx.HTTPError as e:
            logger.exception(f"HTTP 오류: {e}")
            return None
        except Exception as e:
            logger.exception(f"트랜스크립트 전송 오류: {e}")
            return None

    async def notify_meeting_joined(self, meeting_id: str, worker_id: str) -> bool:
        """회의 참여 알림

        Args:
            meeting_id: 회의 ID
            worker_id: 워커 식별자

        Returns:
            성공 여부
        """
        if self._client is None:
            await self.connect()

        if self._client is None:
            return False

        try:
            response = await self._client.post(
                f"/api/v1/meetings/{meeting_id}/worker/joined",
                json={"workerId": worker_id},
            )
            return response.status_code == 200
        except Exception as e:
            logger.exception(f"회의 참여 알림 실패: {e}")
            return False

    async def notify_meeting_left(self, meeting_id: str, worker_id: str) -> bool:
        """회의 퇴장 알림

        Args:
            meeting_id: 회의 ID
            worker_id: 워커 식별자

        Returns:
            성공 여부
        """
        if self._client is None:
            await self.connect()

        if self._client is None:
            return False

        try:
            response = await self._client.post(
                f"/api/v1/meetings/{meeting_id}/worker/left",
                json={"workerId": worker_id},
            )
            return response.status_code == 200
        except Exception as e:
            logger.exception(f"회의 퇴장 알림 실패: {e}")
            return False

    async def update_agent_context(
        self,
        meeting_id: str,
        pre_transcript_id: str,
    ) -> bool:
        """Agent context update 호출

        Args:
            meeting_id: 회의 ID
            pre_transcript_id: 이전 transcript 기준 ID

        Returns:
            성공 여부
        """
        if self._client is None:
            await self.connect()

        if self._client is None:
            return False

        try:
            # meeting_id에서 "meeting-" 접두사 제거
            pure_meeting_id = meeting_id.replace("meeting-", "")

            payload = {
                "meetingId": pure_meeting_id,
                "preTranscriptId": pre_transcript_id,
            }

            response = await self._client.post(
                "/api/v1/agent/meeting/call",
                json=payload,
            )

            if response.status_code == 200:
                logger.info(
                    "Agent context update 성공: meeting_id=%s, pre_transcript_id=%s",
                    meeting_id,
                    pre_transcript_id,
                )
                return True
            else:
                logger.error(
                    "Agent context update 실패: %s - %s",
                    response.status_code,
                    response.text,
                )
                return False

        except Exception as e:
            logger.exception(f"Agent context update 오류: {e}")
            return False

    async def stream_agent_response(
        self,
        meeting_id: str,
        transcript_id: str,
    ) -> AsyncGenerator[dict, None]:
        """Agent 스트리밍 응답 수신 (SSE)

        Args:
            meeting_id: 회의 ID
            transcript_id: 현재 발화 transcript ID
        """
        if self._client is None:
            await self.connect()

        if self._client is None:
            raise RuntimeError("HTTP 클라이언트가 초기화되지 않음")

        # meeting_id에서 "meeting-" 접두사 제거
        pure_meeting_id = meeting_id.replace("meeting-", "")

        payload = {
            "meetingId": pure_meeting_id,
            "transcriptId": transcript_id,
        }

        async with self._client.stream(
            "POST",
            self.config.agent_stream_path,
            json=payload,
            headers={"Accept": "text/event-stream"},
            timeout=None,
        ) as response:
            response.raise_for_status()

            current_event_type = None

            async for line in response.aiter_lines():
                if not line:
                    continue

                # 표준 SSE 형식: "event: type" 또는 "data: content"
                if line.startswith("event: "):
                    current_event_type = line[7:].strip()
                    logger.debug(f"[SSE] event type: {current_event_type}")
                    continue
                
                if not line.startswith("data: "):
                    continue

                data = line[6:].strip()

                if data == "[DONE]":
                    logger.info("[SSE] Stream completed")
                    break
                
                if data.startswith("[ERROR]"):
                    raise RuntimeError(data)

                # 표준 SSE 포맷: event 타입별로 처리
                if current_event_type == "message":
                    logger.debug(f"[SSE] message: {data[:50]}")
                    yield {"type": "message", "content": data}
                elif current_event_type == "status":
                    logger.debug(f"[SSE] status: {data[:50]}")
                    yield {"type": "status", "content": data}
                elif current_event_type == "done":
                    logger.info("[SSE] done")
                    yield {"type": "done"}
                elif current_event_type == "error":
                    logger.error(f"[SSE] error: {data}")
                    yield {"type": "error", "content": data}
