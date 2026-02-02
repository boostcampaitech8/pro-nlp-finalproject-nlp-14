"""Action Item 추출 노드

Decision에서 LLM을 사용해 Action Item을 추출
"""

import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import get_generator_llm
from app.infrastructure.graph.workflows.mit_action.state import (
    MitActionState,
)

logger = logging.getLogger(__name__)


class ActionItemOutput(BaseModel):
    """추출된 Action Item"""

    content: str = Field(description="할 일 내용 (간결하게)")
    due_date: str | None = Field(default=None, description="기한 (YYYY-MM-DD 형식)")
    assignee_name: str | None = Field(default=None, description="담당자 이름 (언급된 경우)")


class ExtractionOutput(BaseModel):
    """LLM 추출 결과"""

    action_items: list[ActionItemOutput] = Field(
        default_factory=list,
        description="추출된 Action Item 목록"
    )


async def extract_actions(state: MitActionState) -> MitActionState:
    """Decision에서 Action Item 추출

    Contract:
        reads: mit_action_decision, mit_action_retry_reason
        writes: mit_action_raw_actions
        side-effects: LLM API 호출 (Clova Studio)
        failures: EXTRACTION_FAILED -> errors 기록
    """
    logger.info("Action Item 추출 시작")

    decision = state.get("mit_action_decision", {})
    retry_reason = state.get("mit_action_retry_reason")

    decision_content = decision.get("content", "")
    decision_context = decision.get("context", "")

    if not decision_content:
        logger.warning("Decision 내용이 비어있습니다")
        return MitActionState(mit_action_raw_actions=[])

    parser = PydanticOutputParser(pydantic_object=ExtractionOutput)

    # 재시도 시 추가 지침 포함
    retry_instruction = ""
    if retry_reason:
        logger.info(f"재시도 사유: {retry_reason}")
        retry_instruction = f"\n\n이전 추출이 거부되었습니다. 사유: {retry_reason}\n이 점을 개선하여 다시 추출하세요."

    prompt = ChatPromptTemplate.from_template(
        "당신은 회의 결정사항에서 Action Item을 추출하는 AI입니다. "
        "반드시 JSON 형식으로만 응답해야 합니다.\n\n"
        "다음 결정사항에서 실행 가능한 Action Item을 추출하세요.\n\n"
        "결정사항:\n{decision_content}\n\n"
        "맥락:\n{decision_context}\n\n"
        "추출 지침:\n"
        "1. 구체적인 할 일만 추출하세요 (모호한 내용 제외)\n"
        "2. 담당자가 언급되면 assignee_name에 기록하세요\n"
        "3. 기한이 언급되면 YYYY-MM-DD 형식으로 due_date에 기록하세요\n"
        "4. Action Item이 없으면 빈 배열을 반환하세요\n"
        "{retry_instruction}\n\n"
        "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
        "{format_instructions}\n\n"
        "예시:\n"
        '{{"action_items": [{{"content": "API 문서 작성", '
        '"due_date": "2026-02-01", "assignee_name": "김철수"}}]}}'
    )

    chain = prompt | get_generator_llm() | parser

    try:
        result = chain.invoke({
            "decision_content": decision_content,
            "decision_context": decision_context,
            "retry_instruction": retry_instruction,
            "format_instructions": parser.get_format_instructions(),
        })

        logger.info(f"Action Item 추출 완료: {len(result.action_items)}개")

        # Pydantic 모델을 dict로 변환
        raw_actions = [
            {
                "content": item.content,
                "due_date": item.due_date,
                "assignee_name": item.assignee_name,
                "assignee_id": None,  # 이름만 추출, ID는 나중에 매칭
                "confidence": 0.8,  # 기본 신뢰도
            }
            for item in result.action_items
        ]

        return MitActionState(mit_action_raw_actions=raw_actions)

    except Exception as e:
        logger.error(f"Action Item 추출 실패: {e}")
        return MitActionState(mit_action_raw_actions=[])
