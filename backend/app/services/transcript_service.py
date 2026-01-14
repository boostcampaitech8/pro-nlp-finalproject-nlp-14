"""회의 트랜스크립트 서비스 (화자별 발화 병합)"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.storage import storage_service
from app.models.meeting import Meeting
from app.models.recording import MeetingRecording, RecordingStatus
from app.models.transcript import MeetingTranscript, TranscriptStatus

logger = logging.getLogger(__name__)


@dataclass
class Utterance:
    """화자별 발화"""

    id: int
    speaker_id: str
    speaker_name: str
    start_ms: int
    end_ms: int
    text: str
    absolute_timestamp: datetime  # 실제 시간 (wall-clock time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "speakerId": self.speaker_id,
            "speakerName": self.speaker_name,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "text": self.text,
            "timestamp": self.absolute_timestamp.isoformat(),  # ISO 8601 형식
        }


class TranscriptService:
    """회의 트랜스크립트 관리 서비스

    - 회의 전체 STT 시작/진행 관리
    - 화자별 발화 병합
    - 회의록 스크립트 생성
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_meeting_with_recordings(
        self,
        meeting_id: UUID,
    ) -> Meeting | None:
        """회의와 녹음 목록 조회"""
        query = (
            select(Meeting)
            .options(selectinload(Meeting.recordings).selectinload(MeetingRecording.user))
            .where(Meeting.id == meeting_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_transcript(self, meeting_id: UUID) -> MeetingTranscript | None:
        """회의 트랜스크립트 조회"""
        query = select(MeetingTranscript).where(
            MeetingTranscript.meeting_id == meeting_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_transcript(
        self,
        meeting_id: UUID,
    ) -> MeetingTranscript:
        """회의 트랜스크립트 조회 또는 생성"""
        transcript = await self.get_transcript(meeting_id)

        if transcript is None:
            transcript = MeetingTranscript(
                meeting_id=meeting_id,
                status=TranscriptStatus.PENDING.value,
            )
            self.db.add(transcript)
            await self.db.commit()
            await self.db.refresh(transcript)

        return transcript

    async def start_transcription(self, meeting_id: UUID) -> MeetingTranscript:
        """회의 전체 STT 시작

        Args:
            meeting_id: 회의 ID

        Returns:
            MeetingTranscript: 생성/업데이트된 트랜스크립트

        Raises:
            ValueError: 회의를 찾을 수 없거나 완료된 녹음이 없음
        """
        meeting = await self.get_meeting_with_recordings(meeting_id)

        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        # 완료된 녹음 필터링
        completed_recordings = [
            r for r in meeting.recordings
            if r.status == RecordingStatus.COMPLETED.value
        ]

        if not completed_recordings:
            raise ValueError("NO_COMPLETED_RECORDINGS")

        # 트랜스크립트 생성/업데이트
        transcript = await self.get_or_create_transcript(meeting_id)
        transcript.status = TranscriptStatus.PROCESSING.value
        transcript.updated_at = datetime.now(timezone.utc)
        transcript.error = None

        await self.db.commit()
        await self.db.refresh(transcript)

        logger.info(
            f"Meeting transcription started: meeting={meeting_id}, "
            f"recordings={len(completed_recordings)}"
        )

        return transcript

    async def get_transcription_status(
        self,
        meeting_id: UUID,
    ) -> dict:
        """STT 진행 상태 조회

        Returns:
            dict: {
                transcriptId, status, totalRecordings,
                processedRecordings, error
            }
        """
        meeting = await self.get_meeting_with_recordings(meeting_id)

        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        transcript = await self.get_transcript(meeting_id)

        if not transcript:
            raise ValueError("TRANSCRIPT_NOT_FOUND")

        # 완료된 녹음과 STT 완료된 녹음 수 계산
        completed_recordings = [
            r for r in meeting.recordings
            if r.status in [
                RecordingStatus.COMPLETED.value,
                RecordingStatus.TRANSCRIBING.value,
                RecordingStatus.TRANSCRIBED.value,
                RecordingStatus.TRANSCRIPTION_FAILED.value,
            ]
        ]

        transcribed_recordings = [
            r for r in meeting.recordings
            if r.status == RecordingStatus.TRANSCRIBED.value
        ]

        return {
            "transcript_id": str(transcript.id),
            "status": transcript.status,
            "total_recordings": len(completed_recordings),
            "processed_recordings": len(transcribed_recordings),
            "error": transcript.error,
        }

    async def merge_utterances(self, meeting_id: UUID) -> MeetingTranscript:
        """화자별 발화 병합

        모든 녹음의 STT 결과를 타임스탬프 기준으로 정렬하여
        화자 라벨이 포함된 회의록 생성

        Args:
            meeting_id: 회의 ID

        Returns:
            MeetingTranscript: 병합된 트랜스크립트
        """
        meeting = await self.get_meeting_with_recordings(meeting_id)

        if not meeting:
            raise ValueError("MEETING_NOT_FOUND")

        transcript = await self.get_transcript(meeting_id)

        if not transcript:
            raise ValueError("TRANSCRIPT_NOT_FOUND")

        # STT 완료된 녹음만 필터링
        transcribed_recordings = [
            r for r in meeting.recordings
            if r.status == RecordingStatus.TRANSCRIBED.value
            and r.transcript_segments
        ]

        if not transcribed_recordings:
            raise ValueError("NO_TRANSCRIBED_RECORDINGS")

        # 모든 세그먼트 수집 (화자 정보 + 실제 시간 포함)
        all_utterances = []
        utterance_id = 0

        for recording in transcribed_recordings:
            user = recording.user
            speaker_name = user.name if user else "Unknown"
            speaker_id = str(recording.user_id)
            recording_start = recording.started_at

            for segment in recording.transcript_segments:
                start_ms = segment.get("startMs", 0)
                end_ms = segment.get("endMs", 0)

                # 실제 시간 계산: 녹음 시작 시각 + 세그먼트 상대 시간
                absolute_timestamp = recording_start + timedelta(milliseconds=start_ms)

                utterance = Utterance(
                    id=utterance_id,
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=segment.get("text", ""),
                    absolute_timestamp=absolute_timestamp,
                )
                all_utterances.append(utterance)
                utterance_id += 1

        # 실제 시간 기준 정렬 (대화 맥락 명확화)
        all_utterances.sort(key=lambda u: u.absolute_timestamp)

        # ID 재할당
        for i, utterance in enumerate(all_utterances):
            utterance.id = i

        # 전체 텍스트 생성 (화자 라벨 + 실제 시간 포함)
        full_text_parts = []
        for utterance in all_utterances:
            timestamp_str = utterance.absolute_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            full_text_parts.append(
                f"[{timestamp_str}] [{utterance.speaker_name}] {utterance.text}"
            )

        full_text = "\n".join(full_text_parts)

        # 메타데이터 계산
        total_duration_ms = 0
        if all_utterances:
            total_duration_ms = max(u.end_ms for u in all_utterances)

        speaker_ids = set(r.user_id for r in transcribed_recordings)
        utterances_dict = [u.to_dict() for u in all_utterances]

        # 회의 시작/종료 시각 계산
        meeting_start = min(r.started_at for r in transcribed_recordings)
        meeting_end = max(
            r.ended_at if r.ended_at else r.started_at
            for r in transcribed_recordings
        )

        # MinIO에 회의록 JSON 파일 업로드
        transcript_json = {
            "meetingId": str(meeting_id),
            "totalDurationMs": total_duration_ms,
            "speakerCount": len(speaker_ids),
            "meetingStart": meeting_start.isoformat(),  # 회의 실제 시작 시각
            "meetingEnd": meeting_end.isoformat(),      # 회의 실제 종료 시각
            "utterances": utterances_dict,
            "fullText": full_text,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        json_data = json.dumps(transcript_json, ensure_ascii=False, indent=2).encode("utf-8")
        file_path = storage_service.upload_transcript(str(meeting_id), json_data)

        logger.info(f"Transcript uploaded to MinIO: {file_path}")

        # 트랜스크립트 업데이트
        transcript.status = TranscriptStatus.COMPLETED.value
        transcript.full_text = full_text
        transcript.utterances = utterances_dict
        transcript.file_path = file_path
        transcript.total_duration_ms = total_duration_ms
        transcript.speaker_count = len(speaker_ids)
        transcript.meeting_start = meeting_start
        transcript.meeting_end = meeting_end
        transcript.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(transcript)

        logger.info(
            f"Meeting transcript merged: meeting={meeting_id}, "
            f"utterances={len(all_utterances)}, "
            f"speakers={len(speaker_ids)}, "
            f"file_path={file_path}"
        )

        return transcript

    async def fail_transcription(
        self,
        meeting_id: UUID,
        error: str,
    ) -> MeetingTranscript:
        """STT 작업 실패 처리"""
        transcript = await self.get_transcript(meeting_id)

        if not transcript:
            raise ValueError("TRANSCRIPT_NOT_FOUND")

        transcript.status = TranscriptStatus.FAILED.value
        transcript.error = error
        transcript.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(transcript)

        logger.error(f"Meeting transcription failed: meeting={meeting_id}, error={error}")
        return transcript

    async def check_all_recordings_processed(self, meeting_id: UUID) -> bool:
        """모든 녹음의 STT 완료 여부 확인"""
        meeting = await self.get_meeting_with_recordings(meeting_id)

        if not meeting:
            return False

        completed_recordings = [
            r for r in meeting.recordings
            if r.status == RecordingStatus.COMPLETED.value
            or r.status == RecordingStatus.TRANSCRIBING.value
            or r.status == RecordingStatus.TRANSCRIBED.value
            or r.status == RecordingStatus.TRANSCRIPTION_FAILED.value
        ]

        if not completed_recordings:
            return False

        # 모든 녹음이 처리 완료(성공 또는 실패)되었는지 확인
        for recording in completed_recordings:
            if recording.status not in [
                RecordingStatus.TRANSCRIBED.value,
                RecordingStatus.TRANSCRIPTION_FAILED.value,
            ]:
                return False

        return True
