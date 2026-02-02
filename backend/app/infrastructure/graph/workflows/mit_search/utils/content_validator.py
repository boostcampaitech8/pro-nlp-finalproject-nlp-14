"""Intent 기반 결과 내용 검증 (P0-2)"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class IntentAwareContentValidator:
    """Intent 유형에 맞게 결과 내용 검증"""

    # Intent별 패턴 (regex 및 키워드)
    INTENT_PATTERNS = {
        "Action": {
            # 액션/할일 패턴
            "keywords": [
                "할 일", "할일", "task", "todo", "담당", "담당자", "진행", "완료", "진행 중",
                "미완료", "미완", "deadline", "마감", "기한", "일정", "예정", "계획",
                "실행", "실행해야", "필요", "요청", "지시", "지정", "배정",
            ],
            "patterns": [
                r"(\w+)가?\s*할\s*일",  # "XXX할 일"
                r"(\w+)\s*담당",  # "XXX 담당"
                r"진행\s*(중|예정)",  # "진행 중/예정"
                r"완료\s*기한|마감\s*일",  # "완료 기한", "마감 일"
                r"\d+년\s*\d+월\s*\d+일.*?(완료|마감|진행|예정)",  # 날짜 + 상태
            ],
            "min_match_count": 1,  # 최소 1개 이상 매치
        },
        "Decision": {
            # 의사결정/결정 패턴
            "keywords": [
                "결정", "결정함", "결정했", "승인", "승인함", "합의", "동의", "확인",
                "논의", "검토", "검토 후", "의견", "제안", "제안함", "위원회",
                "회의", "의사결정", "정책", "정책 변경", "규정", "규칙",
                "방침", "지침", "기준", "기준안",
            ],
            "patterns": [
                r"(\w+)\s*(결정|승인|합의)했",  # "XXX 결정/승인했"
                r"다음과\s*같이\s*(결정|승인|합의)",  # "다음과 같이 결정"
                r"회의에서\s*(결정|승인|논의)",  # "회의에서 결정"
                r"(정책|규정|방침|기준)\s*(변경|수정|확정|결정)",  # "정책 변경" 등
                r"(\w+)\s*위원회.*?(결정|승인)",  # "XXX위원회 결정"
            ],
            "min_match_count": 1,
        },
        "Meeting": {
            # 회의 관련 패턴
            "keywords": [
                "회의", "미팅", "meeting", "논의", "토론", "협의", "브리핑",
                "주간", "월간", "분기", "리뷰", "보고", "보고회",
                "참석", "참석자", "의제", "안건", "발표", "발표자",
                "개최", "예정", "진행", "회의 결과",
            ],
            "patterns": [
                r"(\w+).*?회의",  # "XXX회의"
                r"회의\s*(일시|장소|안건|참석자)",  # "회의 일시/장소" 등
                r"(\d+월\s*\d+일).*?회의",  # "1월 15일 회의"
                r"회의\s*결과|회의\s*내용",  # "회의 결과/내용"
                r"(주간|월간|분기)\s*(회의|리뷰|보고)",  # "주간 회의" 등
            ],
            "min_match_count": 1,
        },
    }

    def __init__(self):
        """초기화"""
        self.logger = logging.getLogger(__name__)

    def validate_content(
        self,
        content: str,
        intent_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """결과 내용이 Intent 유형과 일치하는지 검증

        Args:
            content: 검증할 결과 내용
            intent_type: Intent 유형 (Action, Decision, Meeting)

        Returns:
            alignment_score: 0-1 사이의 일치 점수
            matched_patterns: 매칭된 패턴 목록
            assessment: "높음" / "중간" / "낮음"
        """

        if not intent_type or intent_type not in self.INTENT_PATTERNS:
            # Intent 정보가 없으면 중립적 반환
            return {
                "alignment_score": 0.8,  # 기본값
                "matched_patterns": [],
                "assessment": "중간",
                "reason": "Intent 정보 없음",
            }

        if not content:
            return {
                "alignment_score": 0.0,
                "matched_patterns": [],
                "assessment": "낮음",
                "reason": "빈 내용",
            }

        patterns = self.INTENT_PATTERNS[intent_type]
        matched_patterns = []

        # 1. 키워드 매칭
        keyword_matches = self._match_keywords(content, patterns["keywords"])
        matched_patterns.extend(keyword_matches)

        # 2. 정규식 패턴 매칭
        regex_matches = self._match_patterns(content, patterns["patterns"])
        matched_patterns.extend(regex_matches)

        # 3. 점수 계산
        total_matches = len(set(matched_patterns))  # 중복 제거
        min_required = patterns.get("min_match_count", 1)

        if total_matches >= min_required:
            # 최소 요구사항 충족
            alignment_score = min(0.9 + (total_matches * 0.05), 1.0)
            assessment = "높음"
        elif total_matches > 0:
            # 부분 매칭
            alignment_score = 0.6
            assessment = "중간"
        else:
            # 매칭 없음
            alignment_score = 0.2
            assessment = "낮음"

        self.logger.debug(
            f"Content validation for {intent_type}",
            extra={
                "total_matches": total_matches,
                "alignment_score": alignment_score,
                "assessment": assessment,
            },
        )

        return {
            "alignment_score": alignment_score,
            "matched_patterns": list(set(matched_patterns))[:5],  # 상위 5개만
            "assessment": assessment,
            "match_count": total_matches,
            "min_required": min_required,
        }

    def _match_keywords(self, content: str, keywords: list) -> list:
        """키워드 기반 매칭"""
        matched = []
        content_lower = content.lower()

        for keyword in keywords:
            if keyword in content_lower:
                matched.append(keyword)

        return matched

    def _match_patterns(self, content: str, patterns: list) -> list:
        """정규식 패턴 매칭"""
        matched = []
        content_lower = content.lower()

        for pattern in patterns:
            try:
                if re.search(pattern, content_lower):
                    matched.append(pattern)
            except re.error as e:
                self.logger.warning(f"Invalid regex pattern: {pattern}, error: {e}")
                continue

        return matched

    def enrich_result_with_intent_alignment(
        self,
        result: Dict[str, Any],
        intent_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """결과에 intent_alignment 점수 추가

        Args:
            result: 검색 결과
            intent_type: Intent 유형

        Returns:
            intent_alignment이 추가된 result
        """
        content = result.get("content", "") or result.get("description", "") or ""

        validation = self.validate_content(content, intent_type)

        # 결과에 alignment 정보 추가
        result["intent_alignment"] = validation["alignment_score"]
        result["alignment_assessment"] = validation["assessment"]

        return result
