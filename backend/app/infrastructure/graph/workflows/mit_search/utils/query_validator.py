"""Intent 분석 결과 검증 및 정확도 측정 (Dynamic Entity Loading)"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class IntentConfidenceLevel(Enum):
    """의도 분석 신뢰도 레벨"""
    HIGH = (0.8, 1.0, "높음")  # LLM confidence >= 0.8
    MEDIUM = (0.5, 0.8, "중간")  # LLM confidence 0.5-0.8
    LOW = (0.0, 0.5, "낮음")  # LLM confidence < 0.5

    def __init__(self, min_val: float, max_val: float, label: str):
        self.min_val = min_val
        self.max_val = max_val
        self.label = label


@dataclass
class IntentAnalysisResult:
    """Intent 분석 결과 (검증 전)"""
    intent_type: str
    primary_entity: Optional[str]
    search_focus: str
    confidence: float
    fallback_used: bool = False  # LLM 실패 → 규칙 기반 사용 여부
    rule_conflict: bool = False  # LLM과 규칙 기반 의견 불일치

    def get_confidence_level(self) -> IntentConfidenceLevel:
        """신뢰도 레벨 계산"""
        for level in IntentConfidenceLevel:
            if level.min_val <= self.confidence < level.max_val:
                return level
        return IntentConfidenceLevel.HIGH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "primary_entity": self.primary_entity,
            "search_focus": self.search_focus,
            "confidence": self.confidence,
            "confidence_level": self.get_confidence_level().label,
            "fallback_used": self.fallback_used,
            "rule_conflict": self.rule_conflict
        }


class QueryValidator:
    """검색 쿼리 및 Intent 결과 검증 (Dynamic Entity Loading 지원)"""

    def __init__(self, entity_loader=None):
        """초기화

        Args:
            entity_loader: 동적 엔티티 로드 콜백 함수 (선택)
                async fn(entity_type: str) -> Set[str]
        """
        self.validation_results = []
        self.entity_loader = entity_loader
        self.entity_cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 3600  # 1시간

        # 기본 정적 엔티티 (fallback)
        self.known_users = {
            "신수효", "박준서", "김영훈", "이지현", "정다운",
            "최성훈", "조수진", "이준호", "백준", "황인수", "정성욱"
        }

        # 팀 이름
        self.known_teams = {
            "인프라팀", "데이터팀", "백엔드팀", "프론트엔드팀",
            "마케팅팀", "세일즈팀", "운영팀", "HR팀"
        }

        # 시간 표현
        self.temporal_keywords = {
            "상반기", "하반기", "1월", "2월", "3월", "4월", "5월", "6월",
            "7월", "8월", "9월", "10월", "11월", "12월",
            "지난주", "지난달", "지난달", "이번주", "이번달", "다음주", "다음달"
        }

    def _get_or_load_entities(self, entity_type: str):
        """엔티티 조회 (캐시된 데이터 또는 동적 로드)

        Args:
            entity_type: "users" 또는 "teams"

        Returns:
            엔티티 Set
        """
        import time

        # 캐시 확인
        now = time.time()
        if (entity_type in self.entity_cache and
            now - self.cache_timestamp.get(entity_type, 0) < self.cache_ttl):
            return self.entity_cache[entity_type]

        # 동적 로더가 있으면 사용
        if self.entity_loader:
            try:
                # 동기 호출 (또는 async 래퍼)
                entities = self.entity_loader(entity_type)
                if entities:
                    self.entity_cache[entity_type] = entities
                    self.cache_timestamp[entity_type] = now
                    logger.debug(f"Entities loaded for {entity_type}: {len(entities)} items")
                    return entities
            except Exception as e:
                logger.warning(f"Failed to load entities for {entity_type}: {e}")

        # Fallback: 정적 엔티티 반환
        if entity_type == "users":
            return self.known_users
        elif entity_type == "teams":
            return self.known_teams
        else:
            return set()

    def validate_intent(
        self,
        result: IntentAnalysisResult,
        query: str
    ) -> Dict[str, Any]:
        """Intent 분석 결과 검증

        검증 항목:
        1. Entity validation: 추출된 엔티티가 실제로 존재하는가?
        2. Intent consistency: LLM과 규칙 기반 의견 일치?
        3. Confidence calibration: 신뢰도 점수가 타당한가?
        """

        validation_report = {
            "is_valid": True,
            "issues": [],
            "confidence_level": result.get_confidence_level().label,
            "recommendations": []
        }

        # 1. Entity 검증
        if result.primary_entity:
            if not self._validate_entity(result.primary_entity, result.search_focus):
                validation_report["issues"].append(
                    f"알 수 없는 엔티티: {result.primary_entity} (focus: {result.search_focus})"
                )
                if result.confidence > 0.7:
                    validation_report["recommendations"].append(
                        f"신뢰도({result.confidence})가 높지만 엔티티가 확인되지 않음"
                    )
                validation_report["is_valid"] = False

        # 2. Fallback 사용 확인
        if result.fallback_used:
            validation_report["issues"].append("LLM 실패 후 규칙 기반 분석 사용됨")
            if result.confidence > 0.5:
                validation_report["recommendations"].append(
                    "LLM 실패로 규칙 기반 사용 → 신뢰도 재계산 필요"
                )

        # 3. Rule conflict 확인
        if result.rule_conflict:
            validation_report["issues"].append(
                "LLM과 규칙 기반 의견 불일치"
            )
            validation_report["recommendations"].append(
                "결과 신뢰도 낮음 → 추가 검증 필요"
            )

        # 4. Temporal 표현 검증
        if self._contains_temporal_expression(query):
            if result.search_focus not in ["meta_search", "temporal_search"]:
                validation_report["issues"].append(
                    "시간 표현이 있지만 검색 종류가 temporal_search가 아님"
                )

        # 로깅
        if validation_report["issues"]:
            logger.warning(
                "Intent validation issues",
                extra={
                    "query": query,
                    "intent": result.to_dict(),
                    "issues": validation_report["issues"],
                    "recommendations": validation_report["recommendations"]
                }
            )
        else:
            logger.info(
                "Intent validation passed",
                extra={
                    "query": query,
                    "intent": result.to_dict()
                }
            )

        self.validation_results.append({
            "query": query,
            "result": result,
            "validation": validation_report
        })

        return validation_report

    def _validate_entity(self, entity: str, search_focus: str) -> bool:
        """엔티티 존재 여부 검증 (동적 로드 지원)"""
        if search_focus in ["user_search", "person_search", "Decision", "Meeting", "Agenda", "Action", "Composite"]:
            known_users = self._get_or_load_entities("users")
            return entity in known_users
        if search_focus in ["Team", "team_search", "team_member_search", "TeamMember"]:
            known_users = self._get_or_load_entities("users")
            known_teams = self._get_or_load_entities("teams")
            return entity in known_users or entity in known_teams
        if search_focus in ["meta_search", "entity_search"]:
            # Meta/entity search는 엔티티가 없어도 됨
            return True

        # 알 수 없는 focus 타입
        return False

    def _contains_temporal_expression(self, query: str) -> bool:
        """시간 표현 포함 여부"""
        return any(keyword in query for keyword in self.temporal_keywords)

    def get_validation_summary(self) -> Dict[str, Any]:
        """전체 검증 결과 요약"""
        if not self.validation_results:
            return {
                "total_queries": 0,
                "passed": 0,
                "failed": 0,
                "accuracy": 0.0,
                "issues_by_type": {}
            }

        total = len(self.validation_results)
        passed = sum(
            1 for r in self.validation_results
            if r["validation"]["is_valid"]
        )
        failed = total - passed

        # 이슈 통계
        all_issues = []
        for r in self.validation_results:
            all_issues.extend(r["validation"]["issues"])

        issues_by_type = {}
        for issue in all_issues:
            issue_type = issue.split(":")[0]
            issues_by_type[issue_type] = issues_by_type.get(issue_type, 0) + 1

        return {
            "total_queries": total,
            "passed": passed,
            "failed": failed,
            "accuracy": round(passed / total * 100, 2) if total > 0 else 0.0,
            "issues_by_type": issues_by_type,
            "confidence_distribution": self._get_confidence_distribution()
        }

    def _get_confidence_distribution(self) -> Dict[str, int]:
        """신뢰도 분포"""
        distribution = {level.label: 0 for level in IntentConfidenceLevel}
        for result in self.validation_results:
            level = result["result"].get_confidence_level()
            distribution[level.label] += 1
        return distribution

