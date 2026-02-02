"""Workflows 프롬프트

데이터 처리 워크플로우에서 사용하는 프롬프트 모음.
- extraction: Agenda/Decision/Action 추출
- topic: 토픽 병합/분할
"""

from . import extraction
from . import topic

__all__ = ["extraction", "topic"]
