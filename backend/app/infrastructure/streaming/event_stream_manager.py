"""Event Stream Manager - LangGraph astream_events() 통합

Planner → Tool Execution → Generator 단계별 스트리밍
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from openai import RateLimitError

logger = logging.getLogger(__name__)


async def stream_llm_tokens_only(
    graph: CompiledStateGraph,
    state: dict[str, Any],
    config: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    """오케스트레이션 스트리밍: Planner → Tools → Generator

    이벤트 흐름:
    1. on_chain_start (노드 진입) → 상태 메시지
    2. on_chat_model_stream (Planner/Generator 토큰) → token 이벤트
    3. on_tool_start/on_tool_end (도구 실행) → tool_start/tool_end 이벤트
    4. on_chain_end (노드 종료) → 결과 요약

    Args:
        graph: 컴파일된 LangGraph
        state: 그래프 초기 상태
        config: 그래프 설정

    Yields:
        dict: 필터링된 SSE 이벤트
    """
    logger.info("Starting comprehensive event streaming")

    # state에서 user_input 추출
    user_input = None
    if "messages" in state and len(state["messages"]) > 0:
        first_message = state["messages"][0]
        if hasattr(first_message, "content"):
            user_input = first_message.content
            logger.info(f"[STREAM] user_input extracted: '{user_input[:50] if user_input else ''}...'")
    else:
        logger.warning("[STREAM] No user_input found in state")

    # 노드별 역할 정의
    ORCHESTRATION_NODES = {
        "planner": "planner",
        "mit_tools_analyze": "tools_analyze",
        "mit_tools_search": "tools_search",
        "tools": "tools",  # 새 Tool 시스템 (HITL 지원)
        "evaluator": "evaluator",
        "generator": "generator",
    }

    current_node = None
    token_count = {"planner": 0, "generator": 0}
    node_status_sent = set()  # 이미 상태를 보낸 노드 추적
    
    # MIT Search 관련 state 추적
    mit_search_primary_entity = None  # mit_tools_analyze에서 추출

    try:
        async for event in graph.astream_events(state, config, version="v2"):
            event_type = event.get("event")
            event_name = event.get("name")

            # ===== 1. 노드 진입: 즉시 상태 전송 =====
            if event_type == "on_chain_start":
                if event_name in ORCHESTRATION_NODES:
                    current_node = event_name

                    # Planner: user_input 포함
                    if event_name == "planner":
                        logger.info("[PLANNER] 진입 → 즉시 상태 전송")
                        node_status_sent.add("planner")
                        yield {
                            "type": "node_start",
                            "node": "planner",
                            "tag": "status",
                            "user_input": user_input,  # 추가
                            "timestamp": datetime.now().isoformat(),
                        }

                    # Evaluator만 상태 메시지 전송
                    elif event_name == "evaluator":
                        logger.info("[EVALUATOR] 진입 → 즉시 상태 전송")
                        node_status_sent.add(event_name)
                        yield {
                            "type": "node_start",
                            "node": event_name,
                            "tag": "status",
                            "timestamp": datetime.now().isoformat(),
                        }

                    # MIT Tools Analyze: 의도 분석 단계 (상태 메시지 없음)
                    elif event_name == "mit_tools_analyze":
                        logger.info("[MIT_TOOLS_ANALYZE] 진입 → 의도 분석 시작")
                        current_node = "mit_tools_analyze"
                        # 의도 분석은 빠르므로 별도 메시지 없음

                    # MIT Tools Search: 의도 분석 완료 후 검색 시작 시점에 이벤트 발생
                    elif event_name == "mit_tools_search":
                        logger.info("[MIT_TOOLS_SEARCH] 진입 → 검색 시작")
                        current_node = "mit_tools_search"

                        # mit_tools_analyze에서 캡처한 primary_entity 사용
                        if mit_search_primary_entity:
                            logger.info(f"[MIT_TOOLS_SEARCH] primary_entity: '{mit_search_primary_entity}'")
                            yield {
                                "type": "mit_search_start",
                                "tag": "mit_search",
                                "primary_entity": mit_search_primary_entity,
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            logger.warning("[MIT_TOOLS_SEARCH] primary_entity가 없어서 일반 검색 메시지 표시")
                            yield {
                                "type": "mit_search_start",
                                "tag": "mit_search",
                                "primary_entity": None,  # fallback: 일반 검색 메시지
                                "timestamp": datetime.now().isoformat(),
                            }

                    # Generator: 상태 메시지 전송 안함
                    elif event_name == "generator":
                        logger.info("[GENERATOR] 진입")
                        current_node = "generator"
                        # node_start 이벤트 전송하지 않음

                    # 기타 노드: 일단 진입만 기록
                    else:
                        logger.debug(f"[NODE START] {event_name}")

            # ===== 2. LLM 토큰 스트리밍 (Planner & Generator만) =====
            elif event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")

                if not chunk or not hasattr(chunk, "content") or not chunk.content:
                    continue

                # Planner 토큰 (생각 과정)
                if current_node == "planner":
                    token_count["planner"] += 1
                    logger.debug(f"[PLANNER TOKEN] {chunk.content[:20]}")
                    yield {
                        "type": "token",
                        "tag": "planner_token",
                        "content": chunk.content,
                        "node": "planner",
                        "timestamp": datetime.now().isoformat(),
                    }

                # Generator 토큰 (최종 답변)
                elif current_node == "generator":
                    token_count["generator"] += 1
                    logger.debug(
                        f"[GENERATOR TOKEN] '{chunk.content}' "
                        f"(len={len(chunk.content)}, repr={repr(chunk.content)})"
                    )
                    yield {
                        "type": "token",
                        "tag": "generator_token",
                        "content": chunk.content,
                        "node": "generator",
                        "timestamp": datetime.now().isoformat(),
                    }

                # MIT Tools Analyze 토큰 (의도 분석 과정, 필요시)
                elif current_node == "mit_tools_analyze":
                    logger.debug(f"[MIT_TOOLS_ANALYZE TOKEN] {chunk.content[:20]}")
                    # 토큰 스트리밍 하지 않음 (내부 분석)

                # MIT Tools Search 토큰 (검색 과정, 필요시)
                elif current_node == "mit_tools_search":
                    logger.debug(f"[MIT_TOOLS_SEARCH TOKEN] {chunk.content[:20]}")
                    # 토큰 스트리밍 하지 않음 (내부 검색)

            # ===== 3. 도구 시작 (Tool Execution) =====
            elif event_type == "on_tool_start":
                tool_name = event_name
                tool_input = event.get("data", {}).get("input", {})
                logger.info(f"[TOOL START] {tool_name} with input: {tool_input}")

                yield {
                    "type": "tool_start",
                    "tag": "tool_event",
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "timestamp": datetime.now().isoformat(),
                }

            # ===== 4. 도구 종료 (Tool Result) =====
            elif event_type == "on_tool_end":
                tool_name = event_name
                logger.info(f"[TOOL END] {tool_name}")
                yield {
                    "type": "tool_end",
                    "tag": "tool_event",
                    "tool_name": tool_name,
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                }

            # ===== 5. 노드 종료 (진행 상황 요약) =====
            elif event_type == "on_chain_end":
                # Planning 완료 시 결과 전송
                if event_name == "planner":
                    output = event.get("data", {}).get("output", {})
                    logger.info("[PLANNER] 완료 → planning_result 이벤트 전송")
                    yield {
                        "type": "planning_complete",
                        "tag": "planning_result",
                        "next_subquery": output.get("next_subquery"),
                        "plan": output.get("plan"),
                        "need_tools": output.get("need_tools"),
                        "can_answer": output.get("can_answer"),
                        "timestamp": datetime.now().isoformat(),
                    }

                # MIT Tools Analyze 완료: primary_entity 캡처
                elif event_name == "mit_tools_analyze":
                    output = event.get("data", {}).get("output", {})
                    mit_search_primary_entity = output.get("mit_search_primary_entity")
                    query_intent = output.get("mit_search_query_intent", {})
                    logger.info(
                        f"[MIT_TOOLS_ANALYZE] 완료 → primary_entity='{mit_search_primary_entity}', "
                        f"intent_type={query_intent.get('intent_type')}"
                    )

                elif event_name == "generator":
                    logger.info(f"Generator completed: {token_count['generator']} tokens")

                # === HITL 확인 요청 감지 ===
                elif event_name == "tools":
                    output = event.get("data", {}).get("output", {})
                    if output.get("hitl_status") == "pending":
                        logger.info("[HITL] Confirmation requested")
                        yield {
                            "type": "hitl_request",
                            "tool_name": output.get("hitl_tool_name"),
                            "params": output.get("hitl_extracted_params", {}),
                            "params_display": output.get("hitl_params_display", {}),
                            "message": output.get("hitl_confirmation_message", ""),
                            "required_fields": output.get("hitl_required_fields", []),
                            "display_template": output.get("hitl_display_template"),  # 자연어 템플릿
                            "tag": "hitl",
                            "timestamp": datetime.now().isoformat(),
                        }
                        # HITL pending이면 스트림 즉시 종료 (사용자 확인 대기)
                        return

        # 완료 신호
        logger.info(
            f"Event streaming completed: "
            f"planner={token_count['planner']}, generator={token_count['generator']} tokens"
        )
        yield {
            "type": "done",
            "tag": "internal",
            "timestamp": datetime.now().isoformat(),
        }

    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {e}", exc_info=True)
        yield {
            "type": "error",
            "error": "API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "tag": "internal",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        yield {
            "type": "error",
            "error": str(e),
            "tag": "internal",
            "timestamp": datetime.now().isoformat(),
        }
