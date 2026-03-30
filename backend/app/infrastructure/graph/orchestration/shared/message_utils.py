"""Shared Message Utilities for Orchestration"""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


def extract_last_human_query(messages: list[BaseMessage]) -> str:
    """메시지 리스트에서 마지막 HumanMessage의 content를 추출."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def build_generator_chat_messages(
    system_prompt: str,
    messages: list[BaseMessage],
    window_size: int = 10,
) -> list[BaseMessage]:
    """Generator LLM에 전달할 chat_messages를 구성.

    HCX-DASH-002는 function calling을 지원하므로
    AIMessage(tool_calls)와 ToolMessage를 그대로 전달.
    Planner와 동일하게 메시지 윈도잉 + orphan ToolMessage 필터링 수행.

    Args:
        system_prompt: 시스템 프롬프트 텍스트
        messages: state.messages (add_messages reducer로 누적된 전체 메시지)
        window_size: 최근 메시지 윈도우 크기 (기본 10)

    Returns:
        LLM에 전달할 메시지 리스트
        [SystemMessage, ...windowed messages (HumanMessage, AIMessage, ToolMessage)]
    """
    chat_messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    if not messages:
        return chat_messages

    window = messages[-window_size:]

    # orphan ToolMessage 필터링: AIMessage(tool_calls)와 매칭되지 않는 ToolMessage 제거
    valid_tc_ids = {
        tc["id"]
        for msg in window
        if hasattr(msg, "tool_calls") and msg.tool_calls
        for tc in msg.tool_calls
    }
    for msg in window:
        if msg.type == "tool" and getattr(msg, "tool_call_id", None) not in valid_tc_ids:
            continue
        chat_messages.append(msg)

    return chat_messages


def build_planner_chat_messages(
    system_prompt: str,
    messages: list[BaseMessage],
    window_size: int = 10,
) -> list[BaseMessage]:
    """Planner LLM에 전달할 chat_messages를 구성.

    메시지 윈도잉과 orphan ToolMessage 필터링을 수행.
    HumanMessage는 window에 이미 포함되므로 별도 추가하지 않음.

    Args:
        system_prompt: 시스템 프롬프트 텍스트
        messages: state.messages (add_messages reducer로 누적된 전체 메시지)
        window_size: 최근 메시지 윈도우 크기 (기본 10)

    Returns:
        LLM에 전달할 메시지 리스트 [SystemMessage, ...history messages]
    """
    chat_messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    if messages:
        window = messages[-window_size:]
        # orphan ToolMessage 필터링: AIMessage(tool_calls)와 매칭되지 않는 ToolMessage 제거
        valid_tc_ids = {
            tc["id"]
            for msg in window
            if hasattr(msg, "tool_calls") and msg.tool_calls
            for tc in msg.tool_calls
        }
        for msg in window:
            if msg.type == "tool" and getattr(msg, "tool_call_id", None) not in valid_tc_ids:
                continue
            chat_messages.append(msg)

    return chat_messages
