"""Agenda + Decision 추출 노드

트랜스크립트에서 LLM을 사용해 Agenda와 Decision을 추출
"""

import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import get_pr_generator_llm
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState
from app.prompts.v1.workflows.generate_pr import AGENDA_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class DecisionData(BaseModel):
    """추출된 결정사항"""

    content: str = Field(
        description=(
            "해당 아젠다에서 최종 합의된 단일 결정 내용. "
            "명시적 확정/합의/보류 결정만 포함하고, 액션 아이템/제안/단순 의견은 제외."
        )
    )
    context: str = Field(
        default="",
        description=(
            "결정의 근거/맥락/제약. "
            "결정이 그렇게 정해진 이유를 서술하며 status/승인 정보는 포함하지 않음."
        ),
    )


class AgendaData(BaseModel):
    """추출된 아젠다"""

    topic: str = Field(
        description=(
            "작고 구체적인 아젠다 주제(한 가지 핵심). "
            "커밋 메시지처럼 논의 단위를 잘게 쪼갠 제목."
        )
    )
    description: str = Field(
        default="",
        description=(
            "아젠다의 핵심 논의 내용 요약(1문장 권장). "
            "트랜스크립트 근거 기반으로 작성."
        ),
    )
    decision: DecisionData | None = Field(
        default=None,
        description=(
            "해당 아젠다의 결정사항(Agenda당 최대 1개). "
            "명시적 합의가 없으면 null."
        ),
    )


class ExtractionOutput(BaseModel):
    """LLM 추출 결과"""

    summary: str = Field(
        description=(
            "회의 전체 요약(3-7문장). "
            "핵심 논의 흐름과 결론을 포함."
        )
    )
    agendas: list[AgendaData] = Field(
        description=(
            "트랜스크립트 등장 순으로 정렬된 아젠다 목록. "
            "유사 표현은 병합하고, 근거 없는 항목은 제외."
        )
    )


async def extract_agendas(state: GeneratePrState) -> GeneratePrState:
    """트랜스크립트에서 Agenda와 Decision 추출

    Contract:
        reads: generate_pr_transcript_text
        writes: generate_pr_agendas, generate_pr_summary
        side-effects: LLM API 호출 (Clova Studio)
        failures: 추출 실패 시 빈 결과 반환
    """
    transcript = state.get("generate_pr_transcript_text", "")

    if not transcript:
        logger.warning("트랜스크립트가 비어있습니다")
        return GeneratePrState(
            generate_pr_agendas=[],
            generate_pr_summary="",
        )

    parser = PydanticOutputParser(pydantic_object=ExtractionOutput)

    prompt = ChatPromptTemplate.from_template(AGENDA_EXTRACTION_PROMPT)

    chain = prompt | get_pr_generator_llm() | parser

    try:
        # 트랜스크립트가 너무 길면 truncate
        max_length = 100000  # 토큰 제한 고려
        truncated_transcript = transcript[:max_length]
        if len(transcript) > max_length:
            truncated_transcript += "\n... (truncated)"
            logger.warning(f"트랜스크립트가 {max_length}자로 truncated됨")

        result = chain.invoke({
            "transcript": truncated_transcript,
            "format_instructions": parser.get_format_instructions(),
        })

        logger.info(f"Agenda 추출 완료: {len(result.agendas)}개")
        total_decisions = sum(1 for a in result.agendas if a.decision is not None)
        logger.info(f"Decision 추출 완료: {total_decisions}개")

        # Pydantic 모델을 dict로 변환
        agendas_dict = [
            {
                "topic": a.topic,
                "description": a.description,
                "decision": {"content": a.decision.content, "context": a.decision.context}
                if a.decision
                else None,
            }
            for a in result.agendas
        ]

        return GeneratePrState(
            generate_pr_agendas=agendas_dict,
            generate_pr_summary=result.summary,
        )

    except Exception as e:
        logger.error(f"Agenda/Decision 추출 실패: {e}")
        return GeneratePrState(
            generate_pr_agendas=[],
            generate_pr_summary="",
        )
