"""STT Provider 추상 클래스 및 결과 타입 정의"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    """트랜스크립트 세그먼트 (발화 구간)"""

    id: int
    start_ms: int  # 시작 시간 (밀리초)
    end_ms: int    # 종료 시간 (밀리초)
    text: str      # 해당 구간 텍스트

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "text": self.text,
        }


@dataclass
class TranscriptionResult:
    """STT 변환 결과"""

    text: str                              # 전체 텍스트
    segments: list[TranscriptSegment]      # 타임스탬프 포함 세그먼트
    language: str                          # 감지된 언어 코드
    duration_ms: int                       # 전체 길이 (밀리초)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "segments": [seg.to_dict() for seg in self.segments],
            "language": self.language,
            "durationMs": self.duration_ms,
        }


class STTProvider(ABC):
    """STT Provider 추상 클래스

    OpenAI Whisper, Self-hosted Whisper, 로컬 Whisper 등
    다양한 STT 백엔드를 동일한 인터페이스로 사용할 수 있게 추상화
    """

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "ko",
        **kwargs,
    ) -> TranscriptionResult:
        """음성 데이터를 텍스트로 변환

        Args:
            audio_data: 오디오 파일 바이트 데이터 (WebM, MP3 등)
            language: 우선 언어 코드 (기본: 한국어)
            **kwargs: Provider별 추가 옵션

        Returns:
            TranscriptionResult: 변환 결과 (텍스트, 세그먼트, 언어, 길이)
        """
        pass

    @abstractmethod
    def supports_timestamps(self) -> bool:
        """타임스탬프 지원 여부"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 이름"""
        pass

    @property
    def max_file_size_bytes(self) -> int:
        """최대 파일 크기 (바이트). 기본값: 25MB"""
        return 25 * 1024 * 1024
