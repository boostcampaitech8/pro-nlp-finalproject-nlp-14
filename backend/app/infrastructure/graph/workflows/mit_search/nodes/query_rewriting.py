"""검색 쿼리 최적화를 위한 쿼리 재작성 노드."""

import asyncio
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import MitSearchState
from app.infrastructure.graph.integration.llm import get_query_rewriter_llm

# LLM 캐시 (최대 100개 쿼리 캐싱)
_query_cache: dict[str, str] = {}

logger = logging.getLogger(__name__)


def _normalize_korean_numbers(query: str) -> str:
    """간단한 억/만원 단위 숫자 정규화."""

    def repl_eok(match: re.Match) -> str:
        num = float(match.group(1))
        return f"{int(num * 100_000_000)}원"

    def repl_manwon(match: re.Match) -> str:
        num = float(match.group(1))
        return f"{int(num * 10_000)}원"

    query = re.sub(r"(\d+(?:\.\d+)?)\s*억", repl_eok, query)
    query = re.sub(r"(\d+(?:\.\d+)?)\s*만원", repl_manwon, query)
    return query


def normalize_query(query: str) -> str:
    """LLM 없이도 동작하는 테스트/폴백용 정규화."""
    # 공백 정리
    query = re.sub(r"\s+", " ", query).strip()
    # 영문 소문자 변환
    query = "".join(c.lower() if c.isascii() and c.isalpha() else c for c in query)
    # 숫자 단위 변환
    query = _normalize_korean_numbers(query)
    return query


async def normalize_query_with_llm(query: str) -> str:
    """
    LLM을 사용하여 자연스러운 쿼리를 검색 친화적으로 정규화합니다.
    캐싱으로 동일 쿼리 중복 호출 방지.
        # 캐시 확인
        if query in _query_cache:
            logger.debug(f"Cache hit for query: '{query}'")
            return _query_cache[query]

            # 캐시에 저장 (최대 100개 유지)
            if len(_query_cache) >= 100:
                # 가장 오래된 항목 제거 (FIFO)
                _query_cache.pop(next(iter(_query_cache)))
            _query_cache[query] = normalized

    Examples:
        "0.5억 정도로 예산을 짜기로 했는데 JWT 인증" → "50000000원 예산 JWT 인증"
        "오십억 정도의 예산" → "5000000000원 예산"
    """
    llm = get_query_rewriter_llm()

    system_prompt = """당신은 검색 쿼리 최적화 전문가입니다.
사용자의 자연스러운 한국어 입력을 검색 시스템에 최적화된 형태로 정규화합니다.

정규화 규칙:
1. 한국어 숫자 단위 통일 (억/만/천 → 반드시 아라비아 숫자로)
   - "0.5억" → "50000000원"
   - "오십억" → "5000000000원"
   - "약 5천만원" → "50000000원"
   - "3만개" → "30000개"
   - "삼만" → "30000"
   - 주의: 반드시 숫자(0-9)로만 표현, 한글 숫자(일, 이, 삼...) 사용 금지

2. 띄어쓰기 정리
   - 불필요한 공백 제거
   - 단어 사이 단일 공백만 유지

3. 약자/줄임말 처리
   - "DB" → "데이터베이스" 또는 "DB" (검색 최적화)
   - "JWT", "API" → 그대로 유지 (인식도 좋음)

4. 동의어 통일
   - "인증", "로그인", "authentication" → "인증"
   - "배포", "deploy" → "배포"
   - "구현", "implementation" → "구현"

5. 검색에 불필요한 표현 제거
   - "정도로", "약", "대략", "좀" 등의 수식어 제거
   - "하기로 했는데", "할 때" 등의 시간 표현 단순화

중요: 숫자는 반드시 아라비아 숫자(0-9)로만 표현하세요. 한글 숫자(일, 이, 삼, 만, 억 등)를 그대로 출력하지 마세요.

출력 형식:
- 정규화된 쿼리만 반환하세요
- 설명이나 추가 텍스트는 없이 정규화된 쿼리만 제시합니다"""

    user_message = f"쿼리: {query}"

    try:
        # ainvoke 대신 astream 사용 (더 안정적)
        content = ""
        async for chunk in llm.astream([SystemMessage(system_prompt), HumanMessage(user_message)]):
            if hasattr(chunk, 'content') and chunk.content:
                content += chunk.content

        normalized = content.strip()
        logger.debug(f"LLM normalized: '{query}' → '{normalized}'")
        return normalized

    except Exception as e:
        logger.error(f"LLM normalization failed: {e}", exc_info=True)
        # Fallback: 최소한의 정규화만 수행
        return _minimal_normalize(query)


def _minimal_normalize(query: str) -> str:
    """LLM 실패 시 폴백: 공백 정리, 영문 소문자 통일"""
    import re

    # 공백 정리
    query = re.sub(r"\s+", " ", query).strip()

    # 영문 소문자 통일
    def lowercase_english(text):
        return "".join(c.lower() if c.isascii() and c.isalpha() else c for c in text)

    query = lowercase_english(query)
    return query


async def query_rewriter_async(state: MitSearchState) -> dict:
    """LLM 정규화를 통해 사용자 쿼리를 검색 최적화된 형태로 재작성.

    Contract:
        reads: messages (마지막 메시지에서 사용자 입력 추출)
        writes: mit_search_query
        side-effects: LLM API 호출 (ChatClovaX), 쿼리 캐시 조회/업데이트
        failures: LLM 타임아웃/에러 → 로컬 정규화로 폴백 (normalize_query)

    처리 과정:
    1. state.messages[-1].content에서 원본 쿼리 추출 (또는 message 필드 폴백)
    2. LLM 캐시에서 이전 결과 확인 (최대 100개 FIFO)
    3. 시스템 프롬프트로 LLM 호출 (정규화: 한글 숫자, 띄어쓰기, 동의어)
    4. 캐시에 없으면 결과 저장
    5. 정규화된 쿼리 또는 폴백 결과 반환
    """
    logger.info("Starting LLM-based query rewriting")

    try:
        # 1순위: mit_search_query가 이미 있으면 사용 (replanning 서브-쿼리)
        existing_query = state.get("mit_search_query")
        if existing_query:
            logger.info(f"[Replanning] 기존 mit_search_query 사용: '{existing_query}'")
            return {"mit_search_query": existing_query}
        
        # 2순위: messages 또는 message에서 쿼리 추출
        messages = state.get("messages", [])
        message = state.get("message", "")

        # message 또는 messages에서 원본 쿼리 추출
        if messages:
            last_message = messages[-1]
            original_query = (
                last_message.content if hasattr(last_message, "content") else str(last_message)
            )
        elif message:
            original_query = message
        else:
            raise ValueError("No messages or message field in state")

        # LLM 기반 정규화 (메인 로직)
        normalized_query = await normalize_query_with_llm(original_query)

        # 디버깅: 쿼리가 변경되었을 때만 로그
        if original_query != normalized_query:
            logger.info(f"Query normalized by LLM: '{original_query}' → '{normalized_query}'")
        else:
            logger.info(f"Query unchanged: '{original_query}'")

        return {"mit_search_query": normalized_query}

    except Exception as e:
        logger.error(f"LLM query rewriting failed: {e}", exc_info=True)
        # Fallback: 로컬 정규화 사용
        messages = state.get("messages", [])
        message = state.get("message", "")

        if messages:
            fallback_query = messages[-1].content if messages else ""
        else:
            fallback_query = message

        normalized_fallback = normalize_query(fallback_query)
        logger.warning(f"Using fallback normalized query: '{normalized_fallback}'")
        return {"mit_search_query": normalized_fallback}


def query_rewriter(state: MitSearchState) -> dict:
    """동기 환경(테스트)용 래퍼: LLM 실패 시 로컬 정규화 사용."""
    try:
        return asyncio.run(query_rewriter_async(state))
    except Exception:
        # 테스트/로컬 환경에서 LLM 호출 실패 시 간단 정규화
        messages = state.get("messages", [])
        original_query = messages[-1].content if messages else ""
        normalized_query = normalize_query(original_query)
        return {"mit_search_query": normalized_query}
