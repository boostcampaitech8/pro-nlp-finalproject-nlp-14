import datetime
import operator
from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# State 정의
class OrchestrationState(TypedDict):
    run_id: Annotated[str, "run_id"]
    executed_at: Annotated[datetime.datetime, "current_time"]

    # 채팅 메시지
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: Annotated[str, "user_id"]

    # Planning 관련
    plan: Annotated[str, "current plan"]  # 현재 계획
    need_tools: Annotated[bool, "tools needed"]  # 도구 필요 여부

    # Tool execution 관련
    tool_results: Annotated[str, operator.add]  # mit-Tools 실행 결과 (누적)
    retry_count: Annotated[int, "retry count"]  # 재시도 횟수

    # Evaluation 관련
    evaluation: Annotated[str, "evaluation result"]  # 평가 내용
    evaluation_status: Annotated[str, "evaluation status"]  # "retry", "success", "replanning"
    evaluation_reason: Annotated[str, "evaluation reason"]  # 평가 이유

    # Response
    response: Annotated[str, "final response"]  # 최종 응답 (덮어쓰기)
