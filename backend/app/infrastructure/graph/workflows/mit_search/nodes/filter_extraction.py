"""정형화된 쿼리 파라미터 추출을 위한 필터 추출 노드."""

import asyncio
import json
import logging
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.graph.integration.llm import get_filter_extractor_llm

from ..state import MitSearchState

logger = logging.getLogger(__name__)


def parse_temporal_expressions(query: str) -> dict | None:
    """규칙 기반 시간 표현 파싱 (폴백용).

    Args:
        query: 검색 쿼리 문자열

    Returns:
        {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} 또는 None
    """
    today = datetime.now()

    # 오늘
    if "오늘" in query:
        return {"start": today.strftime("%Y-%m-%d"), "end": today.strftime("%Y-%m-%d")}

    # 어제
    if "어제" in query:
        yesterday = today - timedelta(days=1)
        return {"start": yesterday.strftime("%Y-%m-%d"), "end": yesterday.strftime("%Y-%m-%d")}

    # 지난주 / 금주 / 이번주
    if "지난주" in query or "금주" in query or "이번주" in query:
        # 지난주: 7일 전 ~ 어제
        if "지난주" in query:
            start = today - timedelta(days=7)
            end = today - timedelta(days=1)
        else:  # 이번주/금주
            # 이번주: 월요일 ~ 일요일
            monday = today - timedelta(days=today.weekday())
            end = monday + timedelta(days=6)
            start = monday

        return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}

    # 지난달 / 이번달 / 금월
    if "지난달" in query or "이번달" in query or "금월" in query:
        if "지난달" in query:
            # 지난달 전체
            first_day_this_month = today.replace(day=1)
            last_day_prev_month = first_day_this_month - timedelta(days=1)
            first_day_prev_month = last_day_prev_month.replace(day=1)
            return {
                "start": first_day_prev_month.strftime("%Y-%m-%d"),
                "end": last_day_prev_month.strftime("%Y-%m-%d"),
            }
        else:  # 이번달/금월
            # 이번달: 1일 ~ 말일
            first_day = today.replace(day=1)
            if today.month == 12:
                last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

            return {"start": first_day.strftime("%Y-%m-%d"), "end": last_day.strftime("%Y-%m-%d")}

    # YYYY년 MM월 형식
    import re

    match = re.search(r"(\d{4})년\s*(\d{1,2})월", query)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)

        return {"start": first_day.strftime("%Y-%m-%d"), "end": last_day.strftime("%Y-%m-%d")}

    return None


async def filter_extractor_async(state: MitSearchState) -> dict:
    """LLM 기반 필터 추출 (시간 범위, 엔티티 타입).

    Contract:
        reads: mit_search_query (정규화된 쿼리 문자열)
        writes: mit_search_filters (date_range, entity_types)
        side-effects: LLM API 호출
        failures: LLM 오류/파싱 실패 → 규칙 기반 폴백 추출 사용

    추출 대상:
    - 시간 표현 (지난주, 이번달, YYYY년 MM월 등)
    - 엔티티 타입 (Decision, Meeting, Action)

    Returns:
        mit_search_filters로 State 업데이트
    """
    logger.info("Starting filter extraction")

    try:
        query = state.get("mit_search_query", "")
        if not query:
            return {"mit_search_filters": {"date_range": None, "entity_types": []}}

        # LLM 기반 필터 추출 시도
        filters = await _extract_filters_with_llm(query)

        # LLM이 실패했으면 규칙 기반 추출로 폴백
        if not filters or (not filters.get("date_range") and not filters.get("entity_types")):
            logger.info("LLM extraction failed or empty, using rule-based fallback")
            filters = _extract_filters_with_rules(query)

        date_range = filters.get("date_range")
        entity_types = filters.get("entity_types", [])

        if date_range:
            logger.info(f"Temporal filter detected: {date_range}")
        if entity_types:
            logger.info(f"Entity types detected: {entity_types}")

        return {"mit_search_filters": filters}

    except Exception as e:
        logger.error(f"Filter extraction failed: {e}", exc_info=True)
        # 실패 시 규칙 기반 폴백 사용
        query = state.get("mit_search_query", "")
        filters = _extract_filters_with_rules(query)
        return {"mit_search_filters": filters}


def _extract_filters_with_rules(query: str) -> dict:
    """규칙 기반 필터 추출 (폴백용)."""
    # 시간 범위 추출
    date_range = parse_temporal_expressions(query)

    # 엔티티 타입 추출
    entity_types = []
    if "결정" in query or "decision" in query.lower():
        entity_types.append("Decision")
    if "회의" in query or "meeting" in query.lower():
        entity_types.append("Meeting")
    if "아젠다" in query or "안건" in query or "agenda" in query.lower():
        entity_types.append("Agenda")
    if "액션" in query or "action" in query.lower() or "할일" in query:
        entity_types.append("Action")

    return {"date_range": date_range, "entity_types": entity_types if entity_types else None}


async def _extract_filters_with_llm(query: str) -> dict:
    """LLM으로 필터를 추출하고 JSON으로 파싱."""
    llm = get_filter_extractor_llm()

    system_prompt = """당신은 검색 쿼리에서 필터를 추출하는 시스템입니다.
출력은 반드시 JSON만 반환하세요.

필드:
- date_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} 또는 null
- entity_types: ["Decision", "Meeting", "Agenda", "Action"] 중 해당하는 리스트 또는 null

규칙:
- 날짜가 명확하지 않으면 date_range는 null
- 엔티티 타입이 없으면 entity_types는 null
- 출력은 JSON 단일 객체만 반환
"""

    user_message = f"쿼리: {query}"

    response = await llm.ainvoke(
        [
            SystemMessage(system_prompt),
            HumanMessage(user_message),
        ]
    )

    content = response.content.strip()
    try:
        # 코드펜스 제거
        if content.startswith("```"):
            content = content.strip("`")
            content = content.replace("json", "", 1).strip()

        # JSON 부분만 추출 시도
        if not content.startswith("{"):
            import re
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if match:
                content = match.group(0)

        parsed = json.loads(content)
        date_range = parsed.get("date_range")
        entity_types = parsed.get("entity_types")

        if date_range is not None and not isinstance(date_range, dict):
            date_range = None
        if entity_types is not None and not isinstance(entity_types, list):
            entity_types = None

        return {"date_range": date_range, "entity_types": entity_types}
    except Exception:
        logger.warning("Failed to parse LLM filter JSON, falling back to rules")
        return {}


def filter_extractor(state: MitSearchState) -> dict:
    """동기 테스트용 래퍼."""
    return asyncio.run(filter_extractor_async(state))
