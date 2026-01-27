"""LangGraph 오케스트레이션 설정"""

from app.core.config import get_settings

_settings = get_settings()

# LLM API 키
NCP_CLOVASTUDIO_API_KEY = _settings.ncp_clovastudio_api_key

# Orchestration 설정
MAX_RETRY = 3  # 최대 재시도 횟수
