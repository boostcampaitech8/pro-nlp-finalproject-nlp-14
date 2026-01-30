"""Recency score 계산을 위한 유틸리티 함수."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def parse_datetime(date_value: Any) -> Optional[datetime]:
    """다양한 형식의 날짜 값을 datetime으로 파싱.

    지원 형식:
    - ISO 8601: "2024-01-29T10:00:00", "2024-01-29T10:00:00Z", "2024-01-29T10:00:00.123456"
    - Date only: "2024-01-29"
    - Datetime object: datetime 객체 그대로 반환
    - Unix timestamp: 정수 또는 float (초 단위)

    Args:
        date_value: 날짜 값 (str, datetime, int, float 등)

    Returns:
        파싱된 datetime 객체 또는 None (파싱 실패 시)
    """
    if date_value is None:
        return None

    # 이미 datetime 객체인 경우
    if isinstance(date_value, datetime):
        return date_value

    # Unix timestamp (초 단위)
    if isinstance(date_value, (int, float)):
        try:
            return datetime.fromtimestamp(date_value)
        except (ValueError, OSError):
            return None

    # 문자열 파싱
    if isinstance(date_value, str):
        # ISO 8601 with timezone
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 2024-01-29T10:00:00.123456Z
            "%Y-%m-%dT%H:%M:%SZ",  # 2024-01-29T10:00:00Z
            "%Y-%m-%dT%H:%M:%S.%f",  # 2024-01-29T10:00:00.123456
            "%Y-%m-%dT%H:%M:%S",  # 2024-01-29T10:00:00
            "%Y-%m-%d %H:%M:%S",  # 2024-01-29 10:00:00
            "%Y-%m-%d",  # 2024-01-29
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_value, fmt)
            except (ValueError, TypeError):
                continue

        logger.debug(f"Failed to parse date string: {date_value}")
        return None

    return None


def calculate_recency_score(
    date_value: Any,
    reference_date: Optional[datetime] = None,
    decay_function: str = "exponential",
) -> float:
    """문서의 최신성 점수 계산.

    최신성 점수는 시간에 따라 감소합니다:
    - 최근 7일: 1.0
    - 최근 1개월: 0.9
    - 최근 3개월: 0.75
    - 최근 6개월: 0.6
    - 최근 1년: 0.4
    - 1년 초과: 0.2

    Args:
        date_value: 문서의 날짜 (str, datetime, int 등)
        reference_date: 기준 날짜 (기본값: 현재 시각)
        decay_function: 감쇠 함수 ("exponential", "linear")

    Returns:
        0.0~1.0 범위의 최신성 점수
    """
    parsed_date = parse_datetime(date_value)
    if parsed_date is None:
        return 0.5  # 날짜 정보 없으면 중간 점수

    if reference_date is None:
        reference_date = datetime.now()

    # 시간 차이 계산
    time_diff = reference_date - parsed_date
    days_ago = time_diff.total_seconds() / 86400  # 일 단위로 변환

    # 미래 날짜는 최고 점수
    if days_ago < 0:
        return 1.0

    # 감쇠 함수에 따른 점수 계산
    if decay_function == "exponential":
        # 지수 감쇠: 7일마다 점수가 절반으로 감소
        return _exponential_decay(days_ago)
    elif decay_function == "linear":
        # 선형 감쇠: 1년 후 0점
        return _linear_decay(days_ago)
    else:
        # 기본: 단계별 감쇠
        return _stepped_decay(days_ago)


def _stepped_decay(days_ago: float) -> float:
    """단계별 감쇠 함수.

    - 0~7일: 1.0
    - 7~30일: 0.9
    - 30~90일: 0.75
    - 90~180일: 0.6
    - 180~365일: 0.4
    - 365일~: 0.2
    """
    if days_ago <= 7:
        return 1.0
    elif days_ago <= 30:
        return 0.9
    elif days_ago <= 90:
        return 0.75
    elif days_ago <= 180:
        return 0.6
    elif days_ago <= 365:
        return 0.4
    else:
        return 0.2


def _exponential_decay(days_ago: float, half_life: float = 90.0) -> float:
    """지수 감쇠 함수.

    half_life일마다 점수가 절반으로 감소

    Args:
        days_ago: 경과 일수
        half_life: 반감기 (기본값: 90일)

    Returns:
        0.0~1.0 범위의 점수
    """
    import math
    decay_rate = math.log(2) / half_life
    score = math.exp(-decay_rate * days_ago)
    return max(0.1, min(1.0, score))  # 0.1~1.0 범위로 제한


def _linear_decay(days_ago: float, max_days: float = 365.0) -> float:
    """선형 감쇠 함수.

    max_days일 후 0점이 되도록 선형 감소

    Args:
        days_ago: 경과 일수
        max_days: 최대 일수 (기본값: 365일)

    Returns:
        0.0~1.0 범위의 점수
    """
    if days_ago >= max_days:
        return 0.1  # 최소 0.1점 보장
    return max(0.1, 1.0 - (days_ago / max_days))


def extract_date_from_result(result: Dict[str, Any]) -> Optional[datetime]:
    """검색 결과에서 날짜 필드를 추출.

    우선순위:
    1. created_at (생성 시각)
    2. updated_at (수정 시각)
    3. date (일반 날짜)
    4. timestamp (타임스탬프)

    Args:
        result: 검색 결과 딕셔너리

    Returns:
        추출된 datetime 객체 또는 None
    """
    date_fields = ["created_at", "updated_at", "date", "timestamp"]

    for field in date_fields:
        if field in result:
            parsed = parse_datetime(result[field])
            if parsed:
                logger.debug(f"Extracted date from field '{field}': {parsed}")
                return parsed

    logger.debug("No valid date field found in result")
    return None
