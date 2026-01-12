"""OpenAI Whisper API Provider"""

import logging
from io import BytesIO

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.services.stt.base import STTProvider, TranscriptionResult, TranscriptSegment

logger = logging.getLogger(__name__)


class OpenAIWhisperProvider(STTProvider):
    """OpenAI Whisper API를 사용하는 STT Provider

    특징:
    - 한글 음성 인식 우수
    - 타임스탬프 지원 (verbose_json 형식)
    - 최대 25MB 파일 크기 제한
    - 비용: 분당 $0.006
    """

    def __init__(self, api_key: str | None = None):
        """Provider 초기화

        Args:
            api_key: OpenAI API 키. None이면 설정에서 가져옴
        """
        settings = get_settings()
        self._api_key = api_key or settings.openai_api_key
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """AsyncOpenAI 클라이언트 (lazy initialization)"""
        if self._client is None:
            if not self._api_key:
                raise ValueError("OpenAI API key is not configured")
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "ko",
        **kwargs,
    ) -> TranscriptionResult:
        """OpenAI Whisper API를 사용하여 음성을 텍스트로 변환

        Args:
            audio_data: 오디오 파일 바이트 데이터
            language: 우선 언어 코드 (기본: 한국어)
            **kwargs: 추가 옵션
                - filename: 파일 이름 (기본: recording.webm)
                - prompt: 컨텍스트 힌트

        Returns:
            TranscriptionResult: 변환 결과
        """
        filename = kwargs.get("filename", "recording.webm")
        prompt = kwargs.get("prompt")

        # BytesIO로 파일 객체 생성 (OpenAI SDK는 파일 이름 필요)
        audio_file = BytesIO(audio_data)
        audio_file.name = filename

        logger.info(
            f"Starting OpenAI Whisper transcription: "
            f"size={len(audio_data)} bytes, language={language}"
        )

        # OpenAI Whisper API 호출
        response = await self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="verbose_json",  # 타임스탬프 포함
            timestamp_granularities=["segment"],
            prompt=prompt,
        )

        # 세그먼트 변환 (초 → 밀리초)
        segments = []
        for i, seg in enumerate(response.segments or []):
            segments.append(TranscriptSegment(
                id=i,
                start_ms=int(seg.start * 1000),
                end_ms=int(seg.end * 1000),
                text=seg.text.strip(),
            ))

        # 전체 길이 계산
        duration_ms = 0
        if segments:
            duration_ms = segments[-1].end_ms

        result = TranscriptionResult(
            text=response.text,
            segments=segments,
            language=response.language or language,
            duration_ms=duration_ms,
        )

        logger.info(
            f"OpenAI Whisper transcription completed: "
            f"language={result.language}, segments={len(segments)}, "
            f"duration={duration_ms}ms"
        )

        return result

    def supports_timestamps(self) -> bool:
        """타임스탬프 지원 여부"""
        return True

    @property
    def provider_name(self) -> str:
        """Provider 이름"""
        return "openai_whisper"

    @property
    def max_file_size_bytes(self) -> int:
        """OpenAI Whisper API 최대 파일 크기: 25MB"""
        return 25 * 1024 * 1024
