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
from app.prompt.v1.workflows.mit_action.extraction import (
    ACTION_EXTRACTION_PROMPT,
    ACTION_RETRY_INSTRUCTION,
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
        retry_instruction = ACTION_RETRY_INSTRUCTION.format(retry_reason=retry_reason)

    prompt = ChatPromptTemplate.from_template(ACTION_EXTRACTION_PROMPT)

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
