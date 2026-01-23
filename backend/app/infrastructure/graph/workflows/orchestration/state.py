"""Orchestration State 정의

메인 그래프(Orchestration)의 루트 State입니다.
모든 서브그래프는 이 State를 상속하여 사용합니다.
"""

import datetime
import operator
from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class OrchestrationState(TypedDict):
    """Orchestration 메인 그래프 State

    모든 서브그래프가 상속하는 루트 State입니다.
    서브그래프 전용 필드는 해당 서브그래프 State에 추가합니다.
    """
    # 실행 ID (trace 추적용)
    run_id: Annotated[str, "run_id"]
    # 실행 시각
    executed_at: Annotated[datetime.datetime, "current_time"]

    # 채팅 메시지
    # 대화 메시지 목록 (LangChain 표준 메시지 형식)
    messages: Annotated[List[BaseMessage], add_messages]

    user_id: Annotated[str, "user_id"]
    """요청 사용자 ID"""

    # Planning 관련
    plan: Annotated[str, "current plan"]
    """현재 실행 계획"""

    need_tools: Annotated[bool, "tools needed"]
    """도구 사용 필요 여부"""

    # Tool execution 관련
    tool_results: Annotated[str, operator.add]
    """도구 실행 결과 (누적)"""

    retry_count: Annotated[int, "retry count"]
    """재시도 횟수"""

    # Evaluation 관련
    evaluation: Annotated[str, "evaluation result"]
    """평가 결과"""

    evaluation_status: Annotated[str, "evaluation status"]
    """평가 상태 (success/failure)"""

    evaluation_reason: Annotated[str, "evaluation reason"]
    """평가 사유"""

    # Response
    response: Annotated[str, "final response"]
    """최종 응답"""
