import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.graph.orchestration.state import GraphState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)


class AnalysisOutput(BaseModel):
    analysis: str = Field(description="현재까지의 실행 결과와 계획 분석")
    has_more_tasks: bool = Field(description="추가로 수행할 작업이 있으면 True, 없으면 False")
    next_action: str = Field(description="다음에 수행할 작업 설명 (없으면 빈 문자열)")


def analyzer(state: GraphState):
    """실행 결과를 분석하고 다음 작업이 필요한지 판단하는 노드"""
    logger.info("분석 단계 진입")

    query = state['query']
    plan = state.get('plan', '')
    executed_tools = state.get('executed_tools', [])

    parser = PydanticOutputParser(pydantic_object=AnalysisOutput)

    prompt = ChatPromptTemplate.from_template(
        "당신은 작업 진행 상황을 분석하는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
        "사용자 질문: {query}\n"
        "원래 계획: {plan}\n"
        "지금까지 실행된 도구: {executed_tools}\n\n"
        "현재까지의 진행 상황을 분석하고, 추가 작업이 필요한지 판단하세요.\n"
        "추가 작업이 필요하면 has_more_tasks를 true로, 그렇지 않으면 false로 설정하세요.\n\n"
        "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
        "{format_instructions}\n\n"
        "예시:\n"
        '{{"analysis": "진행 상황 분석", "has_more_tasks": false, "next_action": ""}}'
    )

    chain = prompt | llm | parser

    try:
        result = chain.invoke({
            "query": query,
            "plan": plan,
            "executed_tools": str(executed_tools),
            "format_instructions": parser.get_format_instructions()
        })

        logger.info(f"분석 결과: {result.analysis}")
        logger.info(f"추가 작업 필요: {result.has_more_tasks}")

        return {
            "analysis": result.analysis,
            "has_more_tasks": result.has_more_tasks,
            "next_action": result.next_action
        }

    except Exception as e:
        logger.error(f"분석 단계에서 에러 발생: {e}")
        return {
            "analysis": "분석 실패",
            "has_more_tasks": False,
            "next_action": ""
        }
