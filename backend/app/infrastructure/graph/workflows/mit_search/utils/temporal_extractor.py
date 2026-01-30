"""복잡한 시간 표현을 정확한 날짜 범위로 변환하는 모듈.

지원하는 시간 표현:
- 상대 시간: 오늘, 어제, 지난주, 이번달, 지난달
- 분기: Q1, Q2, Q3, Q4, 1분기, 2분기
- 반기: 상반기, 하반기
- 연도: 올해, 작년, 2023년, 2024년
- 월: 1월, 2월, ..., 12월, 작년 4월
- 복합: 2023년 상반기, Q1 2024
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ContextAwareTemporalExtractor:
    """컨텍스트를 고려한 시간 표현 추출기."""

    def __init__(self, reference_date: Optional[datetime] = None):
        """
        Args:
            reference_date: 기준 날짜 (기본값: 현재 시각)
        """
        self.reference_date = reference_date or datetime.now()
        logger.info(f"TemporalExtractor initialized with reference_date={self.reference_date.date()}")

    def extract_date_range(self, query: str) -> Optional[Dict[str, str]]:
        """쿼리에서 날짜 범위 추출.

        Args:
            query: 자연어 쿼리 (예: "지난주 결정사항")

        Returns:
            {"start": "2024-01-22T00:00:00Z", "end": "2024-01-28T23:59:59Z"} 또는 None
        """
        query = query.lower().strip()

        # 1. 상대 시간 표현
        if "오늘" in query or "today" in query:
            return self._today()
        if "어제" in query or "yesterday" in query:
            return self._yesterday()
        if "그저께" in query or "이틀전" in query or "2일전" in query:
            return self._days_ago(2)
        if "지난주" in query or "last week" in query:
            return self._last_week()
        if "이번주" in query or "this week" in query:
            return self._this_week()
        if "지난달" in query or "last month" in query:
            return self._last_month()
        if "이번달" in query or "this month" in query:
            return self._this_month()

        # 2. 분기 표현
        quarter_match = self._extract_quarter(query)
        if quarter_match:
            return quarter_match

        # 3. 반기 표현
        half_match = self._extract_half_year(query)
        if half_match:
            return half_match

        # 4. 월 표현
        month_match = self._extract_month(query)
        if month_match:
            return month_match

        # 5. 연도 표현
        year_match = self._extract_year(query)
        if year_match:
            return year_match

        # 6. N일/주/개월 전
        relative_match = self._extract_relative_days(query)
        if relative_match:
            return relative_match

        logger.debug(f"No temporal expression found in query: {query}")
        return None

    def _today(self) -> Dict[str, str]:
        """오늘 00:00:00 ~ 23:59:59."""
        start = self.reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
        return self._format_range(start, end)

    def _yesterday(self) -> Dict[str, str]:
        """어제 00:00:00 ~ 23:59:59."""
        yesterday = self.reference_date - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
        return self._format_range(start, end)

    def _days_ago(self, n: int) -> Dict[str, str]:
        """N일 전 00:00:00 ~ 23:59:59."""
        target_day = self.reference_date - timedelta(days=n)
        start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
        return self._format_range(start, end)

    def _this_week(self) -> Dict[str, str]:
        """이번 주 월요일 00:00:00 ~ 일요일 23:59:59."""
        # 0=월요일, 6=일요일
        weekday = self.reference_date.weekday()
        monday = self.reference_date - timedelta(days=weekday)
        sunday = monday + timedelta(days=6)
        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = sunday.replace(hour=23, minute=59, second=59)
        return self._format_range(start, end)

    def _last_week(self) -> Dict[str, str]:
        """지난주 월요일 00:00:00 ~ 일요일 23:59:59."""
        weekday = self.reference_date.weekday()
        last_monday = self.reference_date - timedelta(days=weekday + 7)
        last_sunday = last_monday + timedelta(days=6)
        start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = last_sunday.replace(hour=23, minute=59, second=59)
        return self._format_range(start, end)

    def _this_month(self) -> Dict[str, str]:
        """이번 달 1일 00:00:00 ~ 말일 23:59:59."""
        start = self.reference_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # 다음 달 1일 - 1초
        if self.reference_date.month == 12:
            next_month = self.reference_date.replace(year=self.reference_date.year + 1, month=1, day=1)
        else:
            next_month = self.reference_date.replace(month=self.reference_date.month + 1, day=1)
        end = next_month - timedelta(seconds=1)
        return self._format_range(start, end)

    def _last_month(self) -> Dict[str, str]:
        """지난 달 1일 00:00:00 ~ 말일 23:59:59."""
        if self.reference_date.month == 1:
            last_month_start = self.reference_date.replace(year=self.reference_date.year - 1, month=12, day=1)
        else:
            last_month_start = self.reference_date.replace(month=self.reference_date.month - 1, day=1)

        last_month_start = last_month_start.replace(hour=0, minute=0, second=0, microsecond=0)

        # 이번 달 1일 - 1초
        this_month_start = self.reference_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = this_month_start - timedelta(seconds=1)

        return self._format_range(last_month_start, end)

    def _extract_quarter(self, query: str) -> Optional[Dict[str, str]]:
        """Q1, Q2, Q3, Q4, 1분기, 2분기 등 추출."""
        # Q1 2024, 2024 Q1
        match = re.search(r'q(\d)\s*(\d{4})|(\d{4})\s*q(\d)', query, re.IGNORECASE)
        if match:
            quarter = int(match.group(1) or match.group(4))
            year = int(match.group(2) or match.group(3))
            return self._quarter_range(quarter, year)

        # Q1 (올해), 1분기 (올해)
        match = re.search(r'q(\d)|(\d)분기', query)
        if match:
            quarter = int(match.group(1) or match.group(2))
            year = self.reference_date.year
            return self._quarter_range(quarter, year)

        return None

    def _quarter_range(self, quarter: int, year: int) -> Dict[str, str]:
        """분기 범위 계산.

        Q1: 1월~3월, Q2: 4월~6월, Q3: 7월~9월, Q4: 10월~12월
        """
        if not 1 <= quarter <= 4:
            logger.warning(f"Invalid quarter: {quarter}")
            quarter = 1

        start_month = (quarter - 1) * 3 + 1  # Q1->1, Q2->4, Q3->7, Q4->10
        start = datetime(year, start_month, 1, 0, 0, 0)

        if quarter == 4:
            end = datetime(year, 12, 31, 23, 59, 59)
        else:
            end_month = start_month + 2
            # 말일 계산
            if end_month == 12:
                next_month = datetime(year + 1, 1, 1, 0, 0, 0)
            else:
                next_month = datetime(year, end_month + 1, 1, 0, 0, 0)
            end = next_month - timedelta(seconds=1)

        return self._format_range(start, end)

    def _extract_half_year(self, query: str) -> Optional[Dict[str, str]]:
        """상반기, 하반기 추출."""
        # 2024년 상반기, 상반기 2024
        match = re.search(r'(\d{4})년?\s*상반기|상반기\s*(\d{4})', query)
        if match:
            year = int(match.group(1) or match.group(2))
            return self._half_year_range(1, year)

        match = re.search(r'(\d{4})년?\s*하반기|하반기\s*(\d{4})', query)
        if match:
            year = int(match.group(1) or match.group(2))
            return self._half_year_range(2, year)

        # 상반기 (올해), 하반기 (올해)
        if "상반기" in query:
            return self._half_year_range(1, self.reference_date.year)
        if "하반기" in query:
            return self._half_year_range(2, self.reference_date.year)

        return None

    def _half_year_range(self, half: int, year: int) -> Dict[str, str]:
        """반기 범위 계산.

        상반기(1): 1월~6월, 하반기(2): 7월~12월
        """
        if half == 1:
            start = datetime(year, 1, 1, 0, 0, 0)
            end = datetime(year, 6, 30, 23, 59, 59)
        else:
            start = datetime(year, 7, 1, 0, 0, 0)
            end = datetime(year, 12, 31, 23, 59, 59)

        return self._format_range(start, end)

    def _extract_year(self, query: str) -> Optional[Dict[str, str]]:
        """올해, 작년, 2023년 등 추출."""
        # 작년
        if "작년" in query or "last year" in query:
            year = self.reference_date.year - 1
            return self._year_range(year)

        # 재작년
        if "재작년" in query:
            year = self.reference_date.year - 2
            return self._year_range(year)

        # 올해
        if "올해" in query or "this year" in query or "금년" in query:
            return self._year_range(self.reference_date.year)

        # 2023년, 2024년
        match = re.search(r'(\d{4})년?', query)
        if match:
            year = int(match.group(1))
            # 유효성 검사 (1900~2100)
            if 1900 <= year <= 2100:
                return self._year_range(year)

        return None

    def _year_range(self, year: int) -> Dict[str, str]:
        """연도 범위 계산."""
        start = datetime(year, 1, 1, 0, 0, 0)
        end = datetime(year, 12, 31, 23, 59, 59)
        return self._format_range(start, end)

    def _extract_month(self, query: str) -> Optional[Dict[str, str]]:
        """1월, 2월, ..., 12월, 작년 4월 등 추출."""
        # 작년 4월, 2023년 5월
        match = re.search(r'작년\s*(\d{1,2})월', query)
        if match:
            month = int(match.group(1))
            year = self.reference_date.year - 1
            return self._month_range(year, month)

        match = re.search(r'(\d{4})년\s*(\d{1,2})월', query)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            return self._month_range(year, month)

        # 1월~12월 (올해)
        match = re.search(r'(\d{1,2})월', query)
        if match:
            month = int(match.group(1))
            year = self.reference_date.year
            return self._month_range(year, month)

        return None

    def _month_range(self, year: int, month: int) -> Dict[str, str]:
        """월 범위 계산."""
        if not 1 <= month <= 12:
            logger.warning(f"Invalid month: {month}")
            month = 1

        start = datetime(year, month, 1, 0, 0, 0)

        # 다음 달 1일 - 1초
        if month == 12:
            next_month = datetime(year + 1, 1, 1, 0, 0, 0)
        else:
            next_month = datetime(year, month + 1, 1, 0, 0, 0)
        end = next_month - timedelta(seconds=1)

        return self._format_range(start, end)

    def _extract_relative_days(self, query: str) -> Optional[Dict[str, str]]:
        """N일 전, N주 전, N개월 전 추출."""
        # 3일 전, 5일전
        match = re.search(r'(\d+)일\s*전', query)
        if match:
            days = int(match.group(1))
            return self._days_ago(days)

        # 2주 전, 3주전
        match = re.search(r'(\d+)주\s*전', query)
        if match:
            weeks = int(match.group(1))
            return self._days_ago(weeks * 7)

        # 2개월 전, 3개월전
        match = re.search(r'(\d+)개월\s*전', query)
        if match:
            months = int(match.group(1))
            target_date = self.reference_date
            for _ in range(months):
                if target_date.month == 1:
                    target_date = target_date.replace(year=target_date.year - 1, month=12)
                else:
                    target_date = target_date.replace(month=target_date.month - 1)

            start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # 다음 달 1일 - 1초
            if target_date.month == 12:
                next_month = datetime(target_date.year + 1, 1, 1, 0, 0, 0)
            else:
                next_month = datetime(target_date.year, target_date.month + 1, 1, 0, 0, 0)
            end = next_month - timedelta(seconds=1)

            return self._format_range(start, end)

        return None

    def _format_range(self, start: datetime, end: datetime) -> Dict[str, str]:
        """날짜 범위를 ISO 8601 형식으로 포맷."""
        return {
            "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%S")
        }


# 싱글톤 인스턴스
_extractor_instance: Optional[ContextAwareTemporalExtractor] = None


def get_temporal_extractor() -> ContextAwareTemporalExtractor:
    """싱글톤 TemporalExtractor 반환."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ContextAwareTemporalExtractor()
    return _extractor_instance
