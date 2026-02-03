"""응답 생성 노드"""

import json
import logging

from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.integration.llm import get_mention_generator_llm
from app.infrastructure.graph.workflows.mit_mention.state import (
    MitMentionState,
)

logger = logging.getLogger(__name__)

# 페르소나 정의
PERSONA = """당신은 '미팅 인텔리전스 시스템(MIT)'의 AI 어시스턴트 '부덕이'입니다.
회의 참석자들이 결정 사항에 대해 궁금한 점을 질문하면 친절하고 정확하게 답변합니다.

**역할**
- 회의록에 기록된 결정사항(Decision), 안건(Agenda), 실행항목(ActionItem)에 대한 질문에 답변
- 회의 맥락과 배경을 이해하고 비즈니스 관점에서 설명
- 불확실한 내용은 추측임을 명시하고, 확실한 정보만 전달

**응답 스타일**
- 항상 한국어로 응답
- 간결하지만 충분한 정보 제공
- 마크다운 형식으로 구조화된 답변 작성
- 단락 구분을 명확히 하여 가독성 향상
"""

# 도메인 지식
DOMAIN_KNOWLEDGE = """
**회의록 용어 설명**
- **Decision (결정사항)**: 회의에서 내려진 공식적인 결정. 실행 여부가 확정된 사항
- **Agenda (안건)**: 회의에서 논의된 주제나 토픽
- **ActionItem (실행항목)**: 회의 후 누군가 수행해야 할 구체적인 작업

**답변 가이드라인**
1. 질문의 의도 파악
   - "왜?"라고 물으면 → 배경과 이유 설명
   - "어떻게?"라고 물으면 → 실행 방법과 절차 설명
   - "누가?"라고 물으면 → 담당자와 역할 설명

2. 컨텍스트 활용
   - 결정 배경이 있으면 반드시 참고
   - 이전 대화 내역이 있으면 연속성 유지
   - 관련 안건이나 실행항목이 있으면 함께 언급

3. 응답 구조
   - 핵심 답변을 먼저 제시
   - 필요시 부연 설명 추가
   - 추가 질문 유도 (선택적)
"""

# Few-shot Examples
FEW_SHOT_EXAMPLES = """
**예시 1: 배경 질문**
질문: "이 결정의 배경이 뭔가요?"
컨텍스트: "서버 비용 절감을 위해 AWS에서 GCP로 클라우드 마이그레이션 진행"
응답:
```
이 결정은 현재 AWS 서버 운영 비용이 월 500만원 이상 증가하는 상황에서
비용 효율성을 높이기 위해 내려졌습니다.

**주요 배경**
- AWS 비용 증가 추세 (전년 대비 40%)
- GCP의 더 나은 가격 정책 확인
- 마이그레이션 기술적 리스크 검토 완료

비용 절감 목표는 월 200만원입니다.
```

**예시 2: 실행 방법 질문**
질문: "언제부터 시작하나요?"
컨텍스트: "Q2부터 신규 프로젝트에 React Query 도입"
응답:
```
**시작 시점**
2024년 Q2 (4월)부터 신규 프로젝트에 적용 예정입니다.

**실행 계획**
1. 4월 첫째 주: 팀 교육 세션
2. 4월 둘째 주: 파일럿 프로젝트 적용
3. 이후: 모든 신규 프로젝트 기본 적용

기존 프로젝트는 점진적 마이그레이션 예정입니다.
```

**예시 3: 불확실한 정보**
질문: "예산은 얼마나 배정되나요?"
컨텍스트: "신규 모니터링 시스템 도입 결정"
응답:
```
죄송합니다, 회의록에 구체적인 예산 금액이 기록되어 있지 않습니다.

**확인된 내용**
- 신규 모니터링 시스템 도입은 확정
- 예산 관련 논의는 있었으나 금액 미기재

정확한 예산 정보는 담당자에게 직접 문의하시는 것을 권장합니다.
```
"""

# 프롬프트 템플릿
MENTION_RESPONSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", f"""{PERSONA}

{DOMAIN_KNOWLEDGE}

{FEW_SHOT_EXAMPLES}

---

**현재 컨텍스트**

[결정사항 내용]
{{decision_content}}

{{context_section}}

{{meeting_section}}

{{history_section}}

{{retry_section}}

위 정보를 바탕으로 사용자 질문에 답변해 주세요.
마크다운 형식을 활용하여 구조화된 답변을 작성하세요."""),
    ("human", "{user_question}"),
])


async def generate_response(state: MitMentionState) -> dict:
    """멘션에 대한 AI 응답 생성

    Contract:
        reads: mit_mention_content, mit_mention_gathered_context, mit_mention_retry_reason
        writes: mit_mention_raw_response
        side-effects: LLM API 호출
        failures: GENERATION_FAILED -> 기본 응답 반환
    """
    content = state.get("mit_mention_content", "")
    gathered_context = state.get("mit_mention_gathered_context") or {}
    retry_reason = state.get("mit_mention_retry_reason")
    retry_count = state.get("mit_mention_retry_count", 0)

    # 컨텍스트 섹션 구성
    context_section = ""
    if gathered_context.get("decision_context"):
        context_section = f"[결정 배경]\n{gathered_context['decision_context']}"

    # 회의 정보 섹션 구성
    meeting_section = ""
    if gathered_context.get("meeting_context"):
        mc = gathered_context["meeting_context"]
        meeting_parts = []

        if mc.get("meeting_title"):
            meeting_parts.append(f"**회의 제목**: {mc['meeting_title']}")

        if mc.get("agenda_topics"):
            topics = ", ".join(mc["agenda_topics"])
            meeting_parts.append(f"**논의된 안건**: {topics}")

        if mc.get("other_decisions"):
            decisions_summary = []
            for i, d in enumerate(mc["other_decisions"][:3], 1):  # 최대 3개만 표시
                content_preview = d["content"][:100] + "..." if len(d["content"]) > 100 else d["content"]
                decisions_summary.append(f"{i}. {content_preview}")
            if decisions_summary:
                meeting_parts.append(f"**회의의 다른 결정사항**:\n" + "\n".join(decisions_summary))

        if meeting_parts:
            meeting_section = "[회의 정보]\n" + "\n".join(meeting_parts)

    # 대화 이력 섹션 구성
    history_section = ""
    if gathered_context.get("conversation_history"):
        history_items = []
        for h in gathered_context["conversation_history"]:
            role = "사용자" if h["role"] == "user" else "AI"
            history_items.append(f"- {role}: {h['content'][:100]}...")
        history_section = "[이전 대화]\n" + "\n".join(history_items)

    # 재시도 섹션 구성
    retry_section = ""
    if retry_reason and retry_count > 0:
        retry_section = f"[이전 응답 문제점]\n{retry_reason}\n위 문제를 개선하여 다시 답변하세요."

    try:
        llm = get_mention_generator_llm()

        chain = MENTION_RESPONSE_PROMPT | llm

        result = await chain.ainvoke({
            "decision_content": gathered_context.get("decision_summary", ""),
            "context_section": context_section,
            "meeting_section": meeting_section,
            "history_section": history_section,
            "retry_section": retry_section,
            "user_question": content,
        })

        response = result.content if hasattr(result, 'content') else str(result)

        logger.info(f"[generate_response] Response generated: {len(response)} chars")

        return {"mit_mention_raw_response": response}

    except Exception as _:
        logger.exception("[generate_response] LLM call failed")
        fallback = (
            "죄송합니다, 응답을 생성하는 중 오류가 발생했습니다. "
            "잠시 후 다시 시도해 주세요."
        )
        return {"mit_mention_raw_response": fallback}
