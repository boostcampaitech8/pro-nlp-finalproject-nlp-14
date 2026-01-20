import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.infrastructure.graph.integration.llm import llm
from app.infrastructure.graph.orchestration.state import GraphState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)

class PlanningOutput(BaseModel):
    plan: str = Field(description="사용자의 질문을 해결하기 위한 단계별 계획")
    tool_required: bool = Field(description="검색이나 요약이 필요하면 True, 아니면 False 반환")

# Planning node
def planning(state: GraphState):
    logger.info("Planning 단계 진입")
    query = state['query']

    # 2. 파서 설정: Pydantic 객체를 기반으로 포맷 지시사항 생성
    parser = PydanticOutputParser(pydantic_object=PlanningOutput)

    # 3. 프롬프트: JSON 형식을 지키도록 지시사항({format_instructions}) 주입
    prompt = ChatPromptTemplate.from_template(
        "당신은 계획을 세우는 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.\n\n"
        "사용자 질문: {query}\n\n"
        "이 질문에 대한 답변을 하기 위한 단계별 계획을 세우세요.\n"
        "외부 검색이나 추가 정보가 반드시 필요하다면 tool_required를 true로 설정하세요.\n\n"
        "중요: 다른 텍스트 없이 오직 JSON만 출력하세요!\n\n"
        "{format_instructions}\n\n"
        "예시:\n"
        '{{"plan": "1단계: 검색, 2단계: 분석", "tool_required": true}}'
    )

    # 4. 체인 연결: 프롬프트 -> LLM -> 파서
    # ChatClovaX는 구조화된 출력을 강제하는 API가 다르므로 파서를 체인 뒤에 붙입니다.
    chain = prompt | llm | parser

    # 5. 실행
    # format_instructions를 프롬프트에 주입해야 함
    try:
        result = chain.invoke({
            "query": query,
            "format_instructions": parser.get_format_instructions()
        })

        # result는 이미 PlanningOutput 객체임
        print(f"생성된 Plan:\n{result.plan}")
        print(f"도구 사용 필요 여부: {result.tool_required}")

        # 6. State 업데이트
        tool_signal = "TOOL_REQUIRED" if result.tool_required else ""
        return {"plan": result.plan, "toolcalls": tool_signal}

    except Exception as e:
        logger.error(f"Planning 단계에서 에러 발생: {e}")
        # 에러 발생 시 기본값 반환 처리 (안정성 확보)
        return {"plan": "계획 수립 실패", "toolcalls": ""}
