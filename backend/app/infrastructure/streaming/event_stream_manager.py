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

    # 노드별 역할 정의
    ORCHESTRATION_NODES = {
        "planner": "planner",
        "mit_tools": "tools",
        "evaluator": "evaluator",
        "generator": "generator",
    }

    current_node = None
    token_count = {"planner": 0, "generator": 0}
    node_status_sent = set()  # 이미 상태를 보낸 노드 추적

    try:
        async for event in graph.astream_events(state, config, version="v2"):
            event_type = event.get("event")
            event_name = event.get("name")

            # ===== 1. 노드 진입: 즉시 상태 전송 =====
            if event_type == "on_chain_start":
                if event_name in ORCHESTRATION_NODES:
                    current_node = event_name

                    # Planner: 항상 상태 전송 (Skip 감지 로직 제거)
                    if event_name == "planner":
                        logger.info(f"[PLANNER] 진입 → 즉시 상태 전송")
                        node_status_sent.add("planner")
                        yield {
                            "type": "node_start",
                            "node": "planner",
                            "tag": "status",
                            "timestamp": datetime.now().isoformat(),
                        }

                    # Generator: 항상 상태 전송
                    elif event_name == "generator":
                        logger.info(f"[GENERATOR] 진입 → 즉시 상태 전송")
                        node_status_sent.add("generator")
                        yield {
                            "type": "node_start",
                            "node": "generator",
                            "tag": "status",
                            "timestamp": datetime.now().isoformat(),
                        }

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
                    logger.debug(f"[GENERATOR TOKEN] {chunk.content[:20]}")
                    yield {
                        "type": "token",
                        "tag": "generator_token",
                        "content": chunk.content,
                        "node": "generator",
                        "timestamp": datetime.now().isoformat(),
                    }

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
                tool_output = event.get("data", {}).get("output", "")
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
                if event_name == "generator":
                    logger.info(f"Generator completed: {token_count['generator']} tokens")

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
