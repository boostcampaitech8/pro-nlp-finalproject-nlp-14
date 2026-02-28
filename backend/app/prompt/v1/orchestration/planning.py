"""Planning 프롬프트 - 공용 상수 모음.

Version: 3.3.0
Description: 공용 메시지 상수만 유지 (모드별 프롬프트는 별도 디렉토리)
Changelog:
    3.3.0: Voice/Spotlight 프롬프트를 모드별 디렉토리로 이동
    3.2.0: Voice/Spotlight 프롬프트를 별도 모듈로 분리
    3.1.0: 시스템 프롬프트를 nodes/planning.py에서 분리하여 이동
    3.0.0: bind_tools 전환 - 프롬프트 기반 도구 설명 제거
    2.0.0: 도구 선택 중심으로 전면 개편 (방어적 mit_search 로직 제거)
    1.0.0: 초기 버전 (planning.py에서 분리)
"""

VERSION = "3.3.0"

__all__ = [
    "TOOL_UNAVAILABLE_MESSAGES",
    "VERSION",
]


# =============================================================================
# missing_requirements 대응 메시지 매핑
# =============================================================================

TOOL_UNAVAILABLE_MESSAGES = {
    "weather_api": "죄송합니다. 날씨 정보는 실시간 데이터로 현재 저는 접근할 수 없습니다.",
    "stock_api": "죄송합니다. 금융 정보(주가, 환율 등)는 실시간 데이터로 현재 저는 접근할 수 없습니다.",
    "web_search": "죄송합니다. 인터넷 검색 정보는 현재 저는 접근할 수 없습니다.",
    "mit_action": "죄송합니다. 해당 기능은 현재 지원하지 않습니다.",
    "query_analysis_error": "죄송합니다. 질문을 이해하는 데 어려움이 있습니다.",
}
