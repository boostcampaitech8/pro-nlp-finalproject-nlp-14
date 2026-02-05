import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# 🔧 FIX: tools 패키지 전체를 import하여 query/mutation 도구들이 registry에 등록되도록 함
import app.infrastructure.graph.orchestration.tools  # noqa: F401
from app.infrastructure.graph.integration.llm import get_planner_llm_for_tools
from app.infrastructure.graph.orchestration.state import OrchestrationState
from app.infrastructure.graph.orchestration.tools.registry import (
    InteractionMode,
    get_langchain_tools_for_mode,
    get_tool_category,
    normalize_interaction_mode,
)
from app.prompt.v1.orchestration.planning import (
    TOOL_UNAVAILABLE_MESSAGES,  # noqa: F401  # Re-export for other modules
    build_spotlight_system_prompt,
    build_voice_system_prompt,
)

logger = logging.getLogger(__name__)


async def create_plan(state: OrchestrationState) -> OrchestrationState:
    """계획 수립 노드 - bind_tools 방식

    Contract:
        reads: messages, retry_count, planning_context, tool_results, interaction_mode, user_context
        writes: plan, need_tools, can_answer, selected_tool, tool_category, tool_args
        side-effects: LLM API 호출
        failures: PLANNING_FAILED -> 기본 계획 반환
    """
    logger.info("Planning 단계 진입")

    messages = state.get("messages", [])
    query = messages[-1].content if messages else ""

    # skip_planning 처리 (HITL 응답 시)
    if state.get("skip_planning") and state.get("plan"):
        logger.info("Planning 단계 스킵: 기존 plan 사용")
        logger.info(f"hitl_status 보존: {state.get('hitl_status')}")
        return OrchestrationState(
            plan=state.get("plan", ""),
            need_tools=state.get("need_tools", False),
            can_answer=state.get("can_answer", True),
            missing_requirements=state.get("missing_requirements", []),
            selected_tool=state.get("selected_tool"),
            tool_category=state.get("tool_category"),
            tool_args=state.get("tool_args", {}),
            # HITL 상태 보존 (confirmed/cancelled 상태가 tools 노드에 전달되어야 함)
            hitl_status=state.get("hitl_status"),
        )

    # 모드 및 도구 설정
    mode = normalize_interaction_mode(state.get("interaction_mode", "voice"))

    langchain_tools = get_langchain_tools_for_mode(mode)
    logger.info(f"Interaction mode: {mode.value}, tools count: {len(langchain_tools)}")

    # bind_tools 적용 (thinking 파라미터 없는 LLM 사용)
    llm = get_planner_llm_for_tools()
    llm_with_tools = llm.bind_tools(langchain_tools)

    # 모드별 시스템 프롬프트 (prompts 모듈에서 빌드)
    if mode == InteractionMode.SPOTLIGHT:
        user_context = state.get("user_context", {})
        system_prompt = build_spotlight_system_prompt(user_context)
    else:
        meeting_id = state.get("meeting_id", "unknown")
        system_prompt = build_voice_system_prompt(meeting_id)

    # 이전 도구 실행 결과를 컨텍스트에 포함
    planning_context = state.get("planning_context", "")
    tool_results = state.get("tool_results", "")
    if tool_results:
        if planning_context:
            planning_context = f"[이전 도구 실행 결과]\n{tool_results}\n\n{planning_context}"
        else:
            planning_context = f"[이전 도구 실행 결과]\n{tool_results}"
        logger.info(f"tool_results를 planning_context에 포함 (길이: {len(tool_results)})")

    # 컨텍스트가 있으면 시스템 프롬프트에 추가
    if planning_context:
        system_prompt += f"\n\n[컨텍스트]\n{planning_context}"

    # 메시지 구성
    chat_messages = [SystemMessage(content=system_prompt)]

    # 이전 대화 히스토리 포함 (최근 10개, 현재 메시지 제외)
    if len(messages) > 1:
        for msg in messages[-11:-1]:
            if msg.type == "human":
                chat_messages.append(HumanMessage(content=msg.content))
            else:
                chat_messages.append(AIMessage(content=msg.content))

    # 현재 메시지
    chat_messages.append(HumanMessage(content=query))

    try:
        # 진단 로깅: LLM에 전송되는 도구 정보
        logger.info(f"Tools being sent to LLM: {[t.name for t in langchain_tools]}")
        logger.debug(f"Tool schemas: {[t.args_schema.schema() if t.args_schema else None for t in langchain_tools]}")

        # LLM 호출 (bind_tools 적용된 모델)
        response: AIMessage = await llm_with_tools.ainvoke(chat_messages)

        # 진단 로깅: LLM 응답 분석
        logger.info(f"LLM response type: {type(response).__name__}")
        logger.info(f"Has tool_calls: {bool(response.tool_calls)}")
        if response.tool_calls:
            logger.info(f"tool_calls content: {response.tool_calls}")
        else:
            logger.info(f"Response content (first 200 chars): {str(response.content)[:200]}")

        # tool_calls 파싱
        if response.tool_calls:
            first_call = response.tool_calls[0]
            tool_name = first_call["name"]
            tool_args = first_call.get("args", {})

            tool_category = get_tool_category(tool_name) or "query"

            logger.info(f"도구 선택됨: {tool_name}")
            logger.info(f"도구 인자: {tool_args}")
            logger.info(f"도구 카테고리: {tool_category}")

            return OrchestrationState(
                messages=[response],
                selected_tool=tool_name,
                tool_args=tool_args,
                tool_category=tool_category,
                need_tools=False,
                can_answer=True,
                plan=f"도구 실행: {tool_name}",
                missing_requirements=[],
            )
        else:
            # 도구 없이 직접 응답
            logger.info("도구 없이 직접 응답")
            logger.info(f"응답 내용: {response.content[:100]}..." if response.content else "응답 없음")

            return OrchestrationState(
                messages=[response],
                response=response.content,
                can_answer=True,
                need_tools=False,
                plan="직접 응답",
                selected_tool=None,
                tool_category=None,
                tool_args={},
                missing_requirements=[],
            )

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")
        return OrchestrationState(
            plan="질문 분석 중 오류 발생",
            need_tools=False,
            can_answer=True,
            missing_requirements=["query_analysis_error"],
            selected_tool=None,
            tool_category=None,
            tool_args={},
        )
