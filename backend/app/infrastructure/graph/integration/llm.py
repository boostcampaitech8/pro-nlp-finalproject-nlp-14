"""LangChain LLM 통합 및 용도별 인스턴스 관리.

모델 선택 전략 (실용적 접근):
- HCX-007: 주력 모델 (Cypher 생성, 답변 생성, Planning, 의도 분석 등)
  * v3 API 사용 (langchain-naver 패키지 필요)
  * thinking 파라미터 필수 (effort: 'none', 'low', 'medium', 'high')
  * temperature로 작업별 차별화: 0.05 (Cypher) ~ 0.6 (답변 생성)
  * max_tokens로 출력량 조절: 256 ~ 2048
- DASH: 단순 패턴 변환 전용 (쿼리 정규화, 필터 추출)
  * 빠른 처리 속도 + 비용 효율성
  * temperature 조절로 창의성/정확성 균형
"""

from functools import lru_cache

from langchain_naver import ChatClovaX

from app.infrastructure.graph.config import NCP_CLOVASTUDIO_API_KEY


@lru_cache
def get_base_llm(model: str = "HCX-003", **kwargs) -> ChatClovaX:
    """Base LLM 인스턴스 반환 (cached)

    Args:
        model: 사용할 모델명 (HCX-007, HCX-003, DASH)
        **kwargs: 추가 설정 (temperature, max_tokens, thinking 등)

    Returns:
        ChatClovaX 인스턴스
    """
    if not NCP_CLOVASTUDIO_API_KEY:
        raise ValueError(
            "NCP_CLOVASTUDIO_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 NCP_CLOVASTUDIO_API_KEY를 설정해주세요."
        )

    # 기본값 설정
    default_config = {
        "temperature": 0.5,
        "max_tokens": 1024,
        "model": model,
        "api_key": NCP_CLOVASTUDIO_API_KEY,
    }

    # kwargs로 덮어쓰기
    default_config.update(kwargs)

    return ChatClovaX(**default_config)


def get_planner_llm() -> ChatClovaX:
    """Planning 전용 LLM (낮은 temperature)

    Model: HCX-007
    Use Case: 복잡한 다단계 계획 수립
    temperature: 0.3 (일관성 우선)
    max_tokens: 1024
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.3,
        max_tokens=1024,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        reasoning_effort="none",
    ).with_config(run_name="planner")


def get_mit_action_generator_llm() -> ChatClovaX:
    """Generator 전용 LLM (일반 추출/생성용)

    Model: HCX-003
    Use Case: mit_action 등 일반적인 구조화 추출/텍스트 생성
    temperature: 0.5 (자연스러운 생성)
    max_tokens: 1024 (짧은/중간 길이 결과에 최적화)
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.5,
        max_tokens=1024,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    ).with_config(run_name="generator")


def get_pr_generator_llm() -> ChatClovaX:
    """Generate PR 전용 LLM (긴 구조화 출력 대응).

    Model: HCX-007
    Use Case: 회의 트랜스크립트에서 Agenda/Decision 대량 추출
    temperature: 0.5 (자연스러운 생성 + 일관성 균형)
    max_tokens: 4096 (다수 Agenda/Decision JSON 출력 대응)
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.5,
        max_tokens=4096,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    ).with_config(run_name="pr_generator")


def get_evaluator_llm() -> ChatClovaX:
    """Evaluator 전용 LLM (낮은 temperature)

    Model: HCX-003
    Use Case: 결과 평가 및 검증
    temperature: 0.2 (일관된 평가 기준)
    max_tokens: 512
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.2,
        max_tokens=512,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    ).with_config(run_name="evaluator")


# ============================================================================
# Context Engineering용 LLM 인스턴스
# ============================================================================


def get_context_summarizer_llm() -> ChatClovaX:
    """ContextManager 토픽 분할/요약 전용 LLM.

    Model: HCX-DASH-002
    Use Case: 실시간 회의 토픽 분할 및 요약
    temperature: 0.3 (일관된 요약)
    max_tokens: 2048 (정보 손실 최소화)

    Why HCX-DASH-002?
    - 실시간 처리에 필요한 빠른 응답 속도
    - 비용 효율성 (빈번한 호출에 적합)
    - 요약/분류 작업에 충분한 성능
    """
    return ChatClovaX(
        model="HCX-DASH-002",
        temperature=0.3,
        max_tokens=2048,
        api_key=NCP_CLOVASTUDIO_API_KEY,
    )


# ============================================================================
# MIT Search용 LLM 인스턴스
# ============================================================================


def get_cypher_generator_llm() -> ChatClovaX:
    """Cypher 생성 LLM (정확도 최고).

    Model: HCX-007
    Use Case: Neo4j Cypher 쿼리 생성 (복잡한 그래프 탐색)
    temperature: 0.05 (극도로 일관된 쿼리 - 같은 의도는 항상 같은 구조)
    max_tokens: 1024 (복잡한 multi-hop Cypher 대응)

    Why 낮은 temperature?
    - Cypher 문법 오류는 시스템 장애로 직결
    - Multi-hop 관계 탐색 시 일관성 필요
    - 유동적인 쿼리에 대응하려면 결정론적 패턴 필수
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.05,
        max_tokens=1024,
        api_key=NCP_CLOVASTUDIO_API_KEY,
    ).with_config(run_name="cypher_generator")


def get_answer_generator_llm() -> ChatClovaX:
    """답변 생성 LLM (창의성 중간).

    Model: HCX-DASH-002
    Use Case: 최종 사용자 대면 답변 생성
    temperature: 0.6 (자연스럽고 친근한 답변)
    max_tokens: 2048 (충분한 설명 + 예시 포함)

    Why 높은 temperature?
    - 사용자 경험의 최종 접점 (품질 = 시스템 신뢰도)
    - 여러 검색 결과를 종합하여 일관된 답변 필요
    - 한국어 자연스러움 극대화
    """
    return ChatClovaX(
        model="HCX-DASH-002",
        temperature=0.6,
        max_tokens=2048,
        api_key=NCP_CLOVASTUDIO_API_KEY,
    ).with_config(run_name="answer_generator")


# ============================================================================
# MIT Search 워크플로우 전용 LLM
# ============================================================================

def get_query_intent_analyzer_llm() -> ChatClovaX:
    """쿼리 의도 분석 LLM (경량화).

    Model: HCX-007 (Clova API에서 사용 가능한 모델)
    Use Case: entity/temporal/general/meta 의도 분류
    temperature: 0.3 (일관된 분류)
    max_tokens: 512 (JSON 출력)

    최적화 근거:
    - Pattern recognition 중심 작업 (낮은 complexity)
    - Low temperature (0.3)로 빠른 응답 유도
    - Cost 효율성 + 정확도 > 95% 유지
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.3,
        max_tokens=512,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    ).with_config(run_name="query_intent_analyzer")


def get_result_scorer_llm() -> ChatClovaX:
    """검색 결과 점수 매기기 LLM.

    Model: HCX-007
    Use Case: 검색 결과 relevance 점수 계산
    temperature: 0.2 (일관된 점수 기준)
    max_tokens: 256 (점수 + 간단한 이유)
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.2,
        max_tokens=256,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    ).with_config(run_name="result_scorer")


def get_reranker_llm() -> ChatClovaX:
    """검색 결과 재랭킹 LLM.

    Model: HCX-007
    Use Case: BGE 점수 기반 재랭킹
    temperature: 0.2 (일관된 랭킹)
    max_tokens: 512
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.2,
        max_tokens=512,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    ).with_config(run_name="reranker")


def get_selector_llm() -> ChatClovaX:
    """최종 결과 선택 LLM.

    Model: HCX-007
    Use Case: 재랭킹된 결과에서 최종 답변 선택
    temperature: 0.1 (결정론적 선택)
    max_tokens: 256
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.1,
        max_tokens=256,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    ).with_config(run_name="selector")


# ============================================================================
# MIT Suggestion/Mention 워크플로우 전용 LLM
# ============================================================================


def get_decision_generator_llm() -> ChatClovaX:
    """Decision 생성 LLM (창의적 생성).

    Model: HCX-007
    Use Case: Suggestion 반영한 새 Decision 내용 생성
    temperature: 0.5 (자연스러운 생성 + 일관성 균형)
    max_tokens: 1024 (충분한 Decision 내용)

    Why 중간 temperature?
    - Decision은 정확성과 창의성 모두 필요
    - Suggestion을 자연스럽게 반영해야 함
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.5,
        max_tokens=1024,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "medium"},
    ).with_config(run_name="decision_generator")


# ============================================================================
# 하위 호환성 함수
# ============================================================================

def get_mention_generator_llm() -> ChatClovaX:
    """멘션 응답 생성 LLM (자연스러운 대화체).

    temperature: 0.6 (자연스러운 대화)
    max_tokens: 4096 (충분한 응답 길이, 한국어 고려, 문장 완성 보장)
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.6,
        max_tokens=4096,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    )


def get_llm() -> ChatClovaX:
    """기본 LLM (하위호환성 전용).

    ⚠️ Deprecated: 새로운 코드는 용도별 함수 사용 권장
    - get_planner_llm()
    - get_cypher_generator_llm()
    - get_answer_generator_llm()
    - 등등...

    Model: HCX-003 (기본 모델)

    Returns:
        ChatClovaX: Configured LLM instance
    """
    return ChatClovaX(
        model="HCX-007",
        temperature=0.5,
        max_tokens=512,
        api_key=NCP_CLOVASTUDIO_API_KEY,
        thinking={"effort": "low"},
    )


# 하위 호환성을 위한 변수 export
try:
    llm = get_llm()
except ValueError:
    # 테스트 환경에서는 None으로 초기화
    llm = None
