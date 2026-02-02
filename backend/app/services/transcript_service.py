"""Transcript Service"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.user import AuthProvider, User
from app.schemas.transcript import (
    CreateTranscriptRequest,
    CreateTranscriptResponse,
    GetMeetingTranscriptsResponse,
    UtteranceItem,
)


class TranscriptService:
    """Transcript 관리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

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
