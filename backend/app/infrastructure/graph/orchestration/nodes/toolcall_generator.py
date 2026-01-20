import logging
from typing import Any, Dict

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.graph.orchestration.state import GraphState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


class ToolCallOutput(BaseModel):
    tool_name: str = Field(description="실행할 도구의 이름")
    parameters: Dict[str, Any] = Field(description="도구 실행에 필요한 파라미터")
    reason: str = Field(description="이 도구를 선택한 이유")


def toolcall_generator(state: GraphState):
    """적절한 도구와 파라미터를 생성하는 노드"""
    logger.info("툴콜 생성 단계 진입")

    query = state['query']
    plan = state.get('plan', '')
    next_action = state.get('next_action', '')
    analysis = state.get('analysis', '')

    parser = PydanticOutputParser(pydantic_object=ToolCallOutput)

    # 사용 가능한 도구 목록 (나중에 동적으로 가져오도록 개선)
    available_tools = """
    사용 가능한 도구:
    1. search - 웹 검색 (params: query)
    2. summarize - 텍스트 요약 (params: text)
    3. action - 특정 작업 수행 (params: action_type, details)
    """

    prompt = ChatPromptTemplate.from_template(
        "당신은 적절한 도구를 선택하고 파라미터를 생성하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
        "사용자 질문: {query}\n"
        "원래 계획: {plan}\n"
        "분석 결과: {analysis}\n"
        "다음 수행할 작업: {next_action}\n\n"
        "{available_tools}\n\n"
        "위 정보를 바탕으로 실행할 도구와 파라미터를 생성하세요.\n\n"
        "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
        "{format_instructions}\n\n"
        "예시:\n"
        '{{"tool_name": "search", "parameters": {{"query": "검색어"}}, "reason": "이유"}}'
    )

    chain = prompt | llm | parser

    try:
        result = chain.invoke({
            "query": query,
            "plan": plan,
            "analysis": analysis,
            "next_action": next_action,
            "available_tools": available_tools,
            "format_instructions": parser.get_format_instructions()
        })

        logger.info(f"생성된 도구 호출: {result.tool_name}")
        logger.info(f"파라미터: {result.parameters}")
        logger.info(f"선택 이유: {result.reason}")

        return {
            "tool_to_execute": {
                "name": result.tool_name,
                "params": result.parameters,
                "reason": result.reason
            }
        }

    except Exception as e:
        logger.error(f"툴콜 생성 단계에서 에러 발생: {e}")
        return {
            "tool_to_execute": {
                "name": "error",
                "params": {},
                "reason": "툴콜 생성 실패"
            }
        }
