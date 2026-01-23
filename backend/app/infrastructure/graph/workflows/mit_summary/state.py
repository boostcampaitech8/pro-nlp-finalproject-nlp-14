"""MIT Summary 서브그래프 State 정의

OrchestrationState를 상속하여 MIT Summary 전용 필드를 추가합니다.
"""

from typing import Any
from uuid import UUID

from app.infrastructure.graph.schema.models import (
    Contradiction,
    GTDecision,
    SummaryOutput,
    Utterance,
)
from app.infrastructure.graph.workflows.orchestration import OrchestrationState


class MitSummaryState(OrchestrationState, total=False):
    """MIT Summary 서브그래프 State

    OrchestrationState를 상속하여 회의 요약 생성을 위한 전용 필드를 추가합니다.

    Prefix 규칙: mit_summary_ (디렉토리명 mit_summary/)

    상속된 필드:
    - run_id, executed_at
    - messages, user_id
    - plan, need_tools
    - tool_results, retry_count
    - evaluation, evaluation_status, evaluation_reason
    - response
    """

    # ============================================================
    # MIT Summary 전용 필드 (mit_summary_ prefix)
    # ============================================================

    # --- 추가 입력 (Orchestration에 없는 필드) ---
    team_id: UUID | None
    """팀 ID (회의 소속 팀)"""

    # --- 입력 파라미터 ---
    mit_summary_meeting_id: UUID | None
    """요약할 회의 ID (메타데이터 참조용, 필수 아님)"""

    mit_summary_query: str | None
    """사용자의 요약 요청 원문 (예: "최근 10분 요약해줘")"""

    # --- 중간 데이터 ---
    mit_summary_utterances_raw: list[Utterance] | None
    """messages에서 추출한 발화 데이터 (이미 Orchestration에서 필터링됨)"""

    mit_summary_gt_decisions: list[GTDecision] | None
    """GT에서 조회한 latest Decision 목록 (모순 감지용)"""

    mit_summary_contradictions: list[Contradiction] | None
    """감지된 모순 목록"""

    # --- 출력 결과 ---
    mit_summary_result: SummaryOutput | None
    """구조화된 요약 결과"""

    mit_summary_text: str | None
    """최종 요약 텍스트 (자연어 응답용)"""

    # --- 자체 평가 (Orchestration evaluator 스킵용) ---
    mit_summary_self_evaluation_passed: bool | None
    """MIT Summary 자체 평가 통과 여부

    True이면 Orchestration의 evaluator 노드가 자동으로 success 처리하고
    별도 평가 없이 바로 답변 생성 단계로 넘어갑니다.

    평가 기준:
    - SummaryOutput 생성 성공
    - 최소 길이 요구사항 충족
    - 필수 필드 존재 (overall_summary, key_points)
    """

    mit_summary_self_evaluation_reason: str | None
    """자체 평가 이유 (실패 시 디버깅용)"""

    # --- 메타데이터 ---
    mit_summary_metadata: dict[str, Any] | None
    """요약 생성 메타데이터

    예시:
    {
        "source": "messages",
        "utterance_count": 45,
        "message_count": 50,
        "duration_seconds": 600,
        "generated_at": "2026-01-23T10:15:00"
    }
    """

    # --- 에러 처리 ---
    mit_summary_errors: dict[str, str] | None
    """에러 기록 (노드별)

    예시:
    {
        "extract_utterances": "MESSAGES_EMPTY",
        "generate_summary": "LLM_TIMEOUT"
    }
    """
