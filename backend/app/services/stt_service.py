"""STT(Speech-to-Text) 서비스"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import storage_service
from app.models.recording import MeetingRecording, RecordingStatus
from app.services.audio_preprocessor import AudioPreprocessor
from app.services.stt import STTProviderFactory, TranscriptionResult

logger = logging.getLogger(__name__)


class STTService:
    """개별 녹음에 대한 STT 처리 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._preprocessor = AudioPreprocessor()

    async def get_recording(self, recording_id: UUID) -> MeetingRecording | None:
        """녹음 조회"""
        query = select(MeetingRecording).where(MeetingRecording.id == recording_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def start_transcription(self, recording_id: UUID) -> MeetingRecording:
        """STT 작업 시작 (상태 변경)

        Args:
            recording_id: 녹음 ID

        Returns:
            MeetingRecording: 업데이트된 녹음

        Raises:
            ValueError: 녹음을 찾을 수 없거나 상태가 잘못됨
        """
        recording = await self.get_recording(recording_id)

        if not recording:
            raise ValueError("RECORDING_NOT_FOUND")

        if recording.status != RecordingStatus.COMPLETED.value:
            raise ValueError("RECORDING_NOT_READY")

        # 상태 업데이트
        recording.status = RecordingStatus.TRANSCRIBING.value
        recording.transcription_started_at = datetime.now(timezone.utc)
        recording.transcription_error = None

        await self.db.commit()
        await self.db.refresh(recording)

        logger.info(f"Transcription started: recording={recording_id}")
        return recording

    async def transcribe_recording(
        self,
        recording: MeetingRecording,
        language: str = "ko",
        use_vad: bool = True,
    ) -> TranscriptionResult:
        """녹음 파일 STT 변환

        클라이언트 VAD 메타데이터가 있으면 우선 사용하고,
        없으면 서버에서 VAD 분석을 수행합니다.

        Args:
            recording: 녹음 객체
            language: 우선 언어 코드
            use_vad: VAD 전처리 사용 여부

        Returns:
            TranscriptionResult: STT 결과
        """
        # MinIO에서 파일 다운로드
        file_data = storage_service.get_recording_file(recording.file_path)

        # 클라이언트 VAD 메타데이터 확인
        client_vad = recording.vad_segments
        has_client_vad = client_vad and client_vad.get("segments")

        logger.info(
            f"Processing recording: id={recording.id}, "
            f"size={len(file_data)} bytes, use_vad={use_vad}, "
            f"client_vad={'yes' if has_client_vad else 'no'}"
        )

        # STT Provider 생성
        provider = STTProviderFactory.create()

        if has_client_vad:
            # 클라이언트 VAD 메타데이터 사용 (서버 부하 감소)
            return await self._transcribe_with_client_vad(
                file_data, provider, language, client_vad
            )
        elif use_vad:
            # 서버 VAD로 발화 구간 추출 후 각각 STT
            return await self._transcribe_with_vad(
                file_data, provider, language, recording.started_at
            )
        else:
            # 전체 파일 STT (파일 크기 제한 주의)
            if len(file_data) > provider.max_file_size_bytes:
                # 파일이 너무 크면 MP3로 압축
                file_data = self._preprocessor.convert_to_mp3(file_data)

            return await provider.transcribe(file_data, language=language)

    async def _transcribe_with_client_vad(
        self,
        file_data: bytes,
        provider,
        language: str,
        vad_metadata: dict,
    ) -> TranscriptionResult:
        """클라이언트 VAD 메타데이터 기반 STT

        클라이언트에서 감지한 발화 구간만 추출하여 STT 수행.
        서버에서 VAD 분석을 수행하지 않아 처리 속도 향상.

        Args:
            file_data: 원본 오디오 데이터
            provider: STT Provider
            language: 언어 코드
            vad_metadata: 클라이언트 VAD 메타데이터

        Returns:
            TranscriptionResult: STT 결과
        """
        segments = vad_metadata.get("segments", [])

        if not segments:
            logger.warning("No voice segments in client VAD metadata")
            return TranscriptionResult(
                text="",
                segments=[],
                language=language,
                duration_ms=vad_metadata.get("totalDurationMs", 0),
            )

        logger.info(f"Using client VAD segments: {len(segments)}")

        # 각 구간에서 오디오 추출 및 STT
        all_segments = []
        all_texts = []
        segment_id = 0

        for vad_seg in segments:
            start_ms = vad_seg.get("startMs", 0)
            end_ms = vad_seg.get("endMs", 0)

            try:
                # 해당 구간 오디오 추출
                segment_audio = self._preprocessor.extract_segment(
                    file_data, start_ms, end_ms, output_format="mp3"
                )

                if not segment_audio:
                    continue

                result = await provider.transcribe(
                    segment_audio,
                    language=language,
                )

                # 원본 타임스탬프로 조정
                for seg in result.segments:
                    seg.id = segment_id
                    seg.start_ms += start_ms
                    seg.end_ms += start_ms
                    all_segments.append(seg)
                    segment_id += 1

                all_texts.append(result.text)

            except Exception as e:
                logger.error(
                    f"Failed to transcribe client VAD segment "
                    f"({start_ms}-{end_ms}ms): {e}"
                )
                continue

        # 결과 병합
        full_text = " ".join(all_texts)
        duration_ms = vad_metadata.get("totalDurationMs", 0)

        return TranscriptionResult(
            text=full_text,
            segments=all_segments,
            language=language,
            duration_ms=duration_ms,
        )

    async def _transcribe_with_vad(
        self,
        file_data: bytes,
        provider,
        language: str,
        recording_start: datetime,
    ) -> TranscriptionResult:
        """VAD로 발화 구간 추출 후 STT

        발화 구간만 STT하여 비용/시간 절약
        """
        # 발화 구간 추출
        voice_segments = self._preprocessor.extract_voice_segments(
            file_data, output_format="mp3"
        )

        if not voice_segments:
            logger.warning("No voice segments detected in recording")
            return TranscriptionResult(
                text="",
                segments=[],
                language=language,
                duration_ms=self._preprocessor.get_audio_duration_ms(file_data),
            )

        logger.info(f"Voice segments extracted: {len(voice_segments)}")

        # 각 구간 STT
        all_segments = []
        all_texts = []
        segment_id = 0

        for voice_seg in voice_segments:
            try:
                result = await provider.transcribe(
                    voice_seg.audio_data,
                    language=language,
                )

                # 원본 타임스탬프로 조정
                for seg in result.segments:
                    seg.id = segment_id
                    seg.start_ms += voice_seg.start_ms
                    seg.end_ms += voice_seg.start_ms
                    all_segments.append(seg)
                    segment_id += 1

                all_texts.append(result.text)

            except Exception as e:
                logger.error(
                    f"Failed to transcribe segment "
                    f"({voice_seg.start_ms}-{voice_seg.end_ms}ms): {e}"
                )
                continue

        # 결과 병합
        full_text = " ".join(all_texts)
        duration_ms = self._preprocessor.get_audio_duration_ms(file_data)

        return TranscriptionResult(
            text=full_text,
            segments=all_segments,
            language=language,
            duration_ms=duration_ms,
        )

    async def complete_transcription(
        self,
        recording_id: UUID,
        result: TranscriptionResult,
    ) -> MeetingRecording:
        """STT 작업 완료 처리

        Args:
            recording_id: 녹음 ID
            result: STT 결과

        Returns:
            MeetingRecording: 업데이트된 녹음
        """
        recording = await self.get_recording(recording_id)

        if not recording:
            raise ValueError("RECORDING_NOT_FOUND")

        recording.status = RecordingStatus.TRANSCRIBED.value
        recording.transcript_text = result.text
        recording.transcript_segments = [seg.to_dict() for seg in result.segments]
        recording.transcript_language = result.language
        recording.transcription_completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(recording)

        logger.info(f"Transcription completed: recording={recording_id}")
        return recording

    async def fail_transcription(
        self,
        recording_id: UUID,
        error: str,
    ) -> MeetingRecording:
        """STT 작업 실패 처리

        Args:
            recording_id: 녹음 ID
            error: 에러 메시지

        Returns:
            MeetingRecording: 업데이트된 녹음
        """
        recording = await self.get_recording(recording_id)

        if not recording:
            raise ValueError("RECORDING_NOT_FOUND")

        recording.status = RecordingStatus.TRANSCRIPTION_FAILED.value
        recording.transcription_error = error
        recording.transcription_completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(recording)

        logger.error(f"Transcription failed: recording={recording_id}, error={error}")
        return recording
