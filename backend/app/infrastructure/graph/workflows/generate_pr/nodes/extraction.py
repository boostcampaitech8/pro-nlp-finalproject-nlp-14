"""Agenda + Decision 추출 노드

트랜스크립트에서 LLM을 사용해 Agenda와 Decision을 추출
"""

import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState

logger = logging.getLogger(__name__)


class DecisionData(BaseModel):
    """추출된 결정사항"""

    content: str = Field(description="결정 내용")
    context: str = Field(default="", description="결정 맥락/근거")


class AgendaData(BaseModel):
    """추출된 아젠다"""

    topic: str = Field(description="아젠다 주제")
    description: str = Field(default="", description="아젠다 설명")
    decisions: list[DecisionData] = Field(default_factory=list, description="결정사항 목록")


class ExtractionOutput(BaseModel):
    """LLM 추출 결과"""

    summary: str = Field(description="회의 전체 요약 (2-3문장)")
    agendas: list[AgendaData] = Field(description="추출된 아젠다 목록")


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

    prompt = ChatPromptTemplate.from_template(
        "당신은 회의록 분석 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
        "다음 회의 트랜스크립트를 분석하여 아젠다와 결정사항을 추출하세요.\n\n"
        "트랜스크립트:\n{transcript}\n\n"
        "분석 지침:\n"
        "1. 회의에서 논의된 주요 주제(아젠다)를 식별하세요\n"
        "2. 각 아젠다에서 합의된 결정사항을 추출하세요\n"
        "3. 결정사항이 없는 아젠다는 decisions를 빈 배열로 두세요\n"
        "4. 전체 회의를 2-3문장으로 요약하세요\n\n"
        "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
        "{format_instructions}\n\n"
        "예시:\n"
        '{{"summary": "프로젝트 진행 상황과 다음 스프린트 계획을 논의했습니다.", '
        '"agendas": [{{"topic": "스프린트 리뷰", "description": "지난 스프린트 결과 검토", '
        '"decisions": [{{"content": "다음 스프린트에서 성능 개선 우선", "context": "사용자 피드백 기반"}}]}}]}}'
    )

    chain = prompt | llm | parser

    try:
        # 트랜스크립트가 너무 길면 truncate
        max_length = 8000  # 토큰 제한 고려
        truncated_transcript = transcript[:max_length]
        if len(transcript) > max_length:
            truncated_transcript += "\n... (truncated)"
            logger.warning(f"트랜스크립트가 {max_length}자로 truncated됨")

        result = chain.invoke({
            "transcript": truncated_transcript,
            "format_instructions": parser.get_format_instructions(),
        })

        logger.info(f"Agenda 추출 완료: {len(result.agendas)}개")
        total_decisions = sum(len(a.decisions) for a in result.agendas)
        logger.info(f"Decision 추출 완료: {total_decisions}개")

        # Pydantic 모델을 dict로 변환
        agendas_dict = [
            {
                "topic": a.topic,
                "description": a.description,
                "decisions": [
                    {"content": d.content, "context": d.context}
                    for d in a.decisions
                ],
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
