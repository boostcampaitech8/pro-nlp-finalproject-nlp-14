"""Workflows 프롬프트

데이터 처리 워크플로우에서 사용하는 프롬프트 모음.
- mit_suggestion/: Decision 수정 제안 처리
- mit_mention/: 멘션 질문 응답 생성
- mit_action/: Action Item 추출
- generate_pr/: Agenda/Decision 추출
"""

from . import generate_pr
from . import mit_action
from . import mit_mention
from . import mit_suggestion
__all__ = ["mit_suggestion", "mit_mention", "mit_action", "generate_pr"]
