"""Transcript Service"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.topic_pubsub import publish_topic_update
from app.infrastructure.context import Utterance as ContextUtterance
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.user import AuthProvider, User
from app.schemas.transcript import (
    CreateTranscriptRequest,
    CreateTranscriptResponse,
    GetMeetingTranscriptsResponse,
    UtteranceItem,
)
from app.services.context_runtime import ContextRuntimeState, get_runtime_if_exists

logger = logging.getLogger(__name__)


class TranscriptService:
    """Transcript 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_topic_payload(
        self,
        meeting_id: str,
        runtime: ContextRuntimeState,
    ) -> dict:
        """SSE publish용 토픽 payload 구성."""
        manager = runtime.manager

        topics_data = [
            {
                "id": seg.id,
                "name": seg.name,
                "summary": seg.summary,
                "startTurn": seg.start_utterance_id,
                "endTurn": seg.end_utterance_id,
                "keywords": seg.keywords,
            }
            for seg in manager.l1_segments
        ]
        topics_data.sort(key=lambda t: t["endTurn"], reverse=True)

        return {
            "meetingId": meeting_id,
            "pendingChunks": len(manager._pending_l1_chunks),
            "isL1Running": manager.is_l1_running,
            "currentTopic": manager.current_topic,
            "topics": topics_data,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

    async def _publish_after_l1_idle(
        self,
        meeting_id: str,
        runtime: ContextRuntimeState,
    ) -> None:
        """백그라운드 L1 처리 완료 후 최신 토픽 상태를 재발행."""
        try:
            await runtime.manager.await_l1_idle()

            async with runtime.lock:
                payload = self._build_topic_payload(meeting_id, runtime)

            await publish_topic_update(meeting_id, payload)
            logger.debug("L1 완료 후 토픽 업데이트 발행: meeting_id=%s", meeting_id)
        except Exception as e:
            logger.warning("L1 완료 후 토픽 발행 실패 (비치명적): %s", e)
        finally:
            current_task = asyncio.current_task()
            async with runtime.lock:
                if runtime.topic_publish_task is current_task:
                    runtime.topic_publish_task = None

    async def _sync_to_context_runtime(
        self,
        meeting_id: UUID,
        transcript: Transcript,
    ) -> None:
        """Context 런타임에 발화 동기화 (best-effort, 실패해도 transcript 저장은 성공)

        Args:
            meeting_id: 회의 ID
            transcript: 저장된 발화 객체
        """
        try:
            meeting_id_str = str(meeting_id)
            runtime = get_runtime_if_exists(meeting_id_str)
            if runtime is None:
                return  # 활성 런타임 없음 (미팅룸에 아무도 없음)

            should_publish = False
            publish_data: dict | None = None
            should_publish_after_l1 = False

            async with runtime.lock:
                # L1 상태 저장 (변경 감지용)
                prev_l1_count = len(runtime.manager.l1_segments)
                prev_pending = len(runtime.manager._pending_l1_chunks)

                runtime.last_utterance_id += 1
                utterance = ContextUtterance(
                    id=runtime.last_utterance_id,
                    speaker_id=str(transcript.user_id),
                    speaker_name="",  # 조회 시점에 해결
                    text=transcript.transcript_text,
                    start_ms=transcript.start_ms,
                    end_ms=transcript.end_ms,
                    confidence=transcript.confidence,
                    absolute_timestamp=transcript.created_at or datetime.now(timezone.utc),
                )
                await runtime.manager.add_utterance(utterance)
                runtime.last_processed_start_ms = transcript.start_ms

                # L1 변경 감지 (새 토픽 생성 또는 pending 변경)
                curr_l1_count = len(runtime.manager.l1_segments)
                curr_pending = len(runtime.manager._pending_l1_chunks)

                if curr_l1_count != prev_l1_count or curr_pending != prev_pending:
                    should_publish = True
                    publish_data = self._build_topic_payload(meeting_id_str, runtime)
                    should_publish_after_l1 = curr_pending > 0

                    # 새 L1 청크가 들어온 경우, 완료 시점 publish를 1회 예약
                    if (
                        should_publish_after_l1
                        and (runtime.topic_publish_task is None or runtime.topic_publish_task.done())
                    ):
                        runtime.topic_publish_task = asyncio.create_task(
                            self._publish_after_l1_idle(meeting_id_str, runtime)
                        )

            # Redis 발행 (lock 밖에서)
            if should_publish and publish_data is not None:
                await publish_topic_update(meeting_id_str, publish_data)
                logger.debug(
                    "토픽 업데이트 발행: meeting_id=%s, topics=%d, pending=%d",
                    meeting_id_str,
                    curr_l1_count,
                    curr_pending,
                )

            logger.debug(
                "Context 런타임 동기화 완료: meeting_id=%s, utterance_id=%d",
                meeting_id,
                runtime.last_utterance_id,
            )
        except Exception as e:
            # 실패해도 transcript 저장은 성공해야 함
            logger.warning("Context 런타임 동기화 실패 (비치명적): %s", e)

    async def create_transcript(
        self,
        meeting_id: UUID,
        request: CreateTranscriptRequest,
    ) -> CreateTranscriptResponse:
        """발화 segment 저장 (Worker → Backend)

        Args:
            meeting_id: path에서 받은 meeting_id
            request: body에서 받은 요청 데이터

        Returns:
            CreateTranscriptResponse

        Raises:
            ValueError: validation 실패 시
        """
        # 1. path meeting_id와 body meetingId 일치 확인
        if meeting_id != request.meeting_id:
            raise ValueError("MEETING_ID_MISMATCH")

        # 2. startMs >= 0 (Pydantic에서 이미 체크됨)
        # 3. endMs > startMs
        if request.end_ms <= request.start_ms:
            raise ValueError("INVALID_TIME_RANGE")

        # 4. text는 빈 문자열 불가 (Pydantic min_length=1로 체크됨)

        # 5. DB insert
        transcript = Transcript(
            meeting_id=request.meeting_id,
            user_id=request.user_id,
            start_ms=request.start_ms,
            end_ms=request.end_ms,
            transcript_text=request.text,
            confidence=request.confidence,
            min_confidence=request.min_confidence,
            agent_call=request.agent_call,
            agent_call_keyword=request.agent_call_keyword,
            agent_call_confidence=request.agent_call_confidence,
            status=request.status,
        )

        self.db.add(transcript)
        await self.db.flush()
        await self.db.refresh(transcript)

        # Context 런타임에 즉시 반영 (best-effort)
        await self._sync_to_context_runtime(meeting_id, transcript)

        return CreateTranscriptResponse(
            id=transcript.id,
            created_at=transcript.created_at,
        )

    async def get_meeting_transcripts(
        self, meeting_id: UUID
    ) -> GetMeetingTranscriptsResponse:
        """회의 전체 전사 조회 (Client → Backend)

        Args:
            meeting_id: 회의 ID

        Returns:
            GetMeetingTranscriptsResponse
        """
        # 1. meeting 존재 확인
        meeting_result = await self.db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        meeting = meeting_result.scalar_one_or_none()
        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 2. transcripts 조회 (created_at ASC 정렬)
        result = await self.db.execute(
            select(Transcript, User)
            .join(User, Transcript.user_id == User.id, isouter=True)
            .where(Transcript.meeting_id == meeting_id)
            .order_by(Transcript.created_at.asc(), Transcript.id.asc())
        )
        rows = result.all()

        # 3. transcript가 없으면 빈 응답
        if not rows:
            return GetMeetingTranscriptsResponse(
                meeting_id=meeting_id,
                status="completed",
                full_text="",
                utterances=[],
                total_duration_ms=0,
                speaker_count=0,
                meeting_start=None,
                meeting_end=None,
                created_at=datetime.now(timezone.utc),
            )

        # 4. utterances 생성
        utterances: list[UtteranceItem] = []
        human_speaker_ids: set[UUID] = set()  # system user 제외한 실제 참여자
        max_end_ms = 0

        for transcript, user in rows:
            speaker_name = user.name if user else "Unknown"
            max_end_ms = max(max_end_ms, transcript.end_ms)

            # speaker_count 계산 시 system user (agent) 제외
            if user and user.auth_provider != AuthProvider.SYSTEM.value:
                human_speaker_ids.add(transcript.user_id)

            utterances.append(
                UtteranceItem(
                    id=transcript.id,
                    speaker_id=transcript.user_id,
                    speaker_name=speaker_name,
                    start_ms=transcript.start_ms,
                    end_ms=transcript.end_ms,
                    text=transcript.transcript_text,
                    timestamp=transcript.created_at,
                    status=transcript.status,
                )
            )

        # 5. fullText 조립 (서버에서 조립, DB에 저장하지 않음)
        full_text_lines = [
            f"{utt.speaker_name}: {utt.text}" for utt in utterances
        ]
        full_text = "\n".join(full_text_lines)

        # 6. 응답 생성
        return GetMeetingTranscriptsResponse(
            meeting_id=meeting_id,
            status="completed",
            full_text=full_text,
            utterances=utterances,
            total_duration_ms=max_end_ms,
            speaker_count=len(human_speaker_ids),  # system user 제외
            meeting_start=None,  # 현재 단계에서는 null
            meeting_end=None,    # 현재 단계에서는 null
            created_at=rows[0][0].created_at,  # 첫 번째 transcript의 생성 시간
        )
