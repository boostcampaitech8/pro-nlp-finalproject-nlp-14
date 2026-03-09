"""점수 계산 유틸리티"""

import logging

logger = logging.getLogger(__name__)


class ScoreCalculator:
    """다양한 신호를 조합한 최종 점수 계산"""

    def __init__(
        self,
        fulltext_weight: float = 0.6,
        entity_match_weight: float = 0.2,
        recency_weight: float = 0.2,
    ):
        """점수 가중치 설정
        
        Args:
            fulltext_weight: FULLTEXT 검색 점수 가중치 (0~1)
            entity_match_weight: 엔티티 일치도 가중치 (0~1)
            recency_weight: 최근성 가중치 (0~1)
        """
        self.fulltext_weight = fulltext_weight
        self.entity_match_weight = entity_match_weight
        self.recency_weight = recency_weight

        # 가중치 합이 1.0인지 확인
        total_weight = fulltext_weight + entity_match_weight + recency_weight
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Score weights don't sum to 1.0: {total_weight}")

    def calculate_combined_score(
        self,
        fulltext_score: float,
        entity_match_score: float = 0.5,
        recency_score: float = 0.5,
    ) -> float:
        """여러 신호를 조합하여 최종 점수 계산

        Args:
            fulltext_score: FULLTEXT 검색 점수 (0~2.0 범위, normalized 가능)
            entity_match_score: 엔티티 일치도 (0~1.0)
            recency_score: 최근성 점수 (0~1.0)

        Returns:
            최종 점수 (0~2.0)
        """
        # FULLTEXT 점수 정규화 (0~2.0 범위를 0~1.0으로)
        normalized_fulltext = min(fulltext_score / 2.0, 1.0)

        # 가중치 적용
        combined = (
            normalized_fulltext * self.fulltext_weight
            + entity_match_score * self.entity_match_weight
            + recency_score * self.recency_weight
        )

        return combined

    def calculate_user_match_score(self, user_name: str, matched_user: str) -> float:
        """사용자명 일치도 점수

        Args:
            user_name: 검색한 사용자명
            matched_user: 결과의 사용자명

        Returns:
            일치도 점수 (0~1.0)
            - 1.0: 완전 일치
            - 0.7: 포함 관계
            - 0.0: 불일치
        """
        if not user_name or not matched_user:
            return 0.5  # 기본값

        user_name = user_name.strip()
        matched_user = matched_user.strip()

        if user_name == matched_user:
            return 1.0  # 완전 일치
        elif user_name in matched_user or matched_user in user_name:
            return 0.7  # 부분 일치
        else:
            return 0.0  # 불일치

    def calculate_recency_score(self, created_at_timestamp: float, now: float) -> float:
        """문서의 나이를 기반으로 최근성 점수 계산

        Args:
            created_at_timestamp: 문서 생성 시간 (Unix timestamp)
            now: 현재 시간 (Unix timestamp)

        Returns:
            최근성 점수 (0~1.0)
            - 1.0: 오늘
            - 0.7: 1주일 이내
            - 0.4: 1개월 이내
            - 0.1: 그 이상
        """
        if not created_at_timestamp or not now:
            return 0.5  # 기본값

        age_seconds = max(0, now - created_at_timestamp)
        age_days = age_seconds / (24 * 3600)

        if age_days <= 1:
            return 1.0
        elif age_days <= 7:
            return 0.7
        elif age_days <= 30:
            return 0.4
        else:
            return 0.1


# 사용 예시
"""
calculator = ScoreCalculator(
    fulltext_weight=0.6,
    entity_match_weight=0.2,
    recency_weight=0.2
)

# 조합 점수 계산
final_score = calculator.calculate_combined_score(
    fulltext_score=1.5,  # FULLTEXT에서 반환된 점수
    entity_match_score=1.0,  # 사용자명 완전 일치
    recency_score=0.7  # 1주일 이내
)
# → 1.5*0.3 + 1.0*0.2 + 0.7*0.2 = 0.45 + 0.2 + 0.14 = 0.79

# 개별 점수 계산
user_score = calculator.calculate_user_match_score("신수효", "신수효")  # 1.0
recency = calculator.calculate_recency_score(created_at_ts, now_ts)  # 0.0~1.0
"""
