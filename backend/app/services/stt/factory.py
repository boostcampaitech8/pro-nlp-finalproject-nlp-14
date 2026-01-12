"""STT Provider 팩토리"""

from app.core.config import get_settings
from app.services.stt.base import STTProvider
from app.services.stt.openai_provider import OpenAIWhisperProvider


class STTProviderFactory:
    """STT Provider 팩토리

    설정에 따라 적절한 STT Provider를 생성
    지원 Provider:
    - openai: OpenAI Whisper API
    - local: 로컬 Whisper 모델 (향후 구현)
    - self_hosted: 자체 호스팅 Whisper API (향후 구현)
    """

    _providers: dict[str, type[STTProvider]] = {
        "openai": OpenAIWhisperProvider,
    }

    @classmethod
    def create(cls, provider_type: str | None = None) -> STTProvider:
        """STT Provider 인스턴스 생성

        Args:
            provider_type: Provider 타입. None이면 설정에서 가져옴

        Returns:
            STTProvider: 생성된 Provider 인스턴스

        Raises:
            ValueError: 지원하지 않는 Provider 타입
        """
        if provider_type is None:
            settings = get_settings()
            provider_type = settings.stt_provider

        provider_class = cls._providers.get(provider_type)
        if provider_class is None:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown STT provider: {provider_type}. "
                f"Available providers: {available}"
            )

        return provider_class()

    @classmethod
    def register(cls, name: str, provider_class: type[STTProvider]) -> None:
        """새로운 Provider 등록

        Args:
            name: Provider 이름
            provider_class: Provider 클래스
        """
        cls._providers[name] = provider_class

    @classmethod
    def available_providers(cls) -> list[str]:
        """사용 가능한 Provider 목록"""
        return list(cls._providers.keys())
