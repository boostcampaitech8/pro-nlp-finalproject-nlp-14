"""검색 결과의 관련성 점수 계산 (Semantic + Intent-Aware)"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from .recency_calculator import calculate_recency_score, extract_date_from_result

logger = logging.getLogger(__name__)


class SearchResultRelevanceScorer:
    """검색 결과의 관련성을 의미론적으로 평가"""

    # Focus 기반 적응형 가중치
    FOCUS_SPECIFIC_WEIGHTS = {
        "Decision": {
            "keyword_match": 0.2,
            "semantic_similarity": 0.4,
            "entity_presence": 0.2,
            "recency": 0.05,  # 낮음 (오래된 결정도 중요)
            "rank_position": 0.15,
        },
        "Action": {
            "keyword_match": 0.3,
            "semantic_similarity": 0.25,
            "entity_presence": 0.25,
            "recency": 0.15,  # 높음 (진행중인 과제가 중요)
            "rank_position": 0.05,
        },
        "Meeting": {
            "keyword_match": 0.25,
            "semantic_similarity": 0.35,
            "entity_presence": 0.15,
            "recency": 0.2,  # 높음 (최근 회의가 중요)
            "rank_position": 0.05,
        },
    }

    # 기본 가중치 (Focus 불명확할 때)
    DEFAULT_WEIGHTS = {
        "keyword_match": 0.25,
        "semantic_similarity": 0.35,
        "entity_presence": 0.15,
        "recency": 0.1,
        "rank_position": 0.15,
    }

    def __init__(self, embedding_model=None):
        """초기화

        Args:
            embedding_model: SentenceTransformer 등의 임베딩 모델 (선택)
        """
        self.weights = self.DEFAULT_WEIGHTS.copy()
        self.embedding_model = embedding_model

    def get_adaptive_weights(self, search_focus: Optional[str]) -> Dict[str, float]:
        """Focus에 맞는 적응형 가중치 반환"""
        if search_focus in self.FOCUS_SPECIFIC_WEIGHTS:
            return self.FOCUS_SPECIFIC_WEIGHTS[search_focus].copy()
        return self.DEFAULT_WEIGHTS.copy()

    def score_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        expected_entity: Optional[str] = None,
        search_focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        """결과 목록의 관련성을 종합 점수로 계산.

        Args:
            results: 검색 결과 목록
            query: 원본 검색 쿼리
            expected_entity: 예상되는 엔티티 (선택)
            search_focus: 검색 포커스 (Decision, Action, Meeting)

        Returns:
            quality_score: 0-100 사이의 종합 점수
            assessment: "높음" / "중간" / "낮음"
            details: 상세 정보
        """

        if not results:
            return {
                "quality_score": 0.0,
                "assessment": "결과없음",
                "result_count": 0,
                "details": {
                    "reason": "검색 결과 없음",
                },
            }

        # Focus에 맞게 가중치 적응
        adaptive_weights = self.get_adaptive_weights(search_focus)

        scores = []
        for idx, result in enumerate(results):
            item_score = self._score_single_result(
                result,
                idx,
                len(results),
                expected_entity,
                search_focus,
                query,
                adaptive_weights,
            )
            scores.append(item_score)

        # 상위 5개 결과 기준으로 평가
        top_scores = [s["total_score"] for s in scores[:5]]
        overall_score = sum(top_scores) / len(top_scores) if top_scores else 0

        assessment = self._assess_quality(overall_score, len(results))

        logger.info(
            "Search result relevance scored",
            extra={
                "query": query,
                "result_count": len(results),
                "quality_score": round(overall_score, 2),
                "assessment": assessment,
                "search_focus": search_focus,
            },
        )

        average_score = (
            sum(item["total_score"] for item in scores) / len(scores)
            if scores
            else 0.0
        )

        return {
            "quality_score": round(overall_score, 2),
            "assessment": assessment,
            "result_count": len(results),
            "top_result_score": round(top_scores[0], 2) if top_scores else 0,
            "average_score": round(average_score, 2),
            "details": {
                "weights": adaptive_weights,
                "top_5_scores": [round(s, 2) for s in top_scores],
                "search_focus": search_focus,
            },
        }

    def _score_single_result(
        self,
        result: Dict[str, Any],
        position: int,
        total_results: int,
        expected_entity: Optional[str],
        search_focus: Optional[str],
        query: str,
        weights: Dict[str, float],
    ) -> Dict[str, Any]:
        """단일 결과의 점수 계산"""

        scores = {}

        # 1. Keyword Match score (FULLTEXT 스코어)
        keyword_score = min(result.get("score", 0) / 10, 1.0)  # Normalize
        scores["keyword_match"] = keyword_score * weights.get("keyword_match", 0.25)

        # 2. Semantic Similarity (의미적 유사도)
        semantic_score = self._calculate_semantic_similarity(result, query)
        scores["semantic_similarity"] = semantic_score * weights.get("semantic_similarity", 0.35)

        # 3. Entity presence (예상 엔티티 포함 여부)
        entity_score = self._check_entity_presence(result, expected_entity)
        scores["entity_presence"] = entity_score * weights.get("entity_presence", 0.15)

        # 4. Recency (최신성, Focus 기반으로 조정됨)
        recency_score = self._calculate_recency(result)
        scores["recency"] = recency_score * weights.get("recency", 0.1)

        # 5. Rank position (결과 내 위치)
        rank_score = 1 - (position / total_results) if total_results > 0 else 1
        scores["rank_position"] = rank_score * weights.get("rank_position", 0.15)

        # Intent alignment 고려 (결과가 실제로 content를 포함하는지)
        intent_alignment = result.get("intent_alignment", 0.8)

        total_score = sum(scores.values())

        # Intent alignment가 낮으면 페널티 적용
        if intent_alignment < 0.3:
            total_score *= 0.5
        elif intent_alignment < 0.6:
            total_score *= 0.8
        # else: 패널티 없음 (intent_alignment >= 0.6)

        total_score = min(total_score, 1.0)  # Cap at 1.0

        return {
            "position": position,
            "component_scores": scores,
            "intent_alignment": intent_alignment,
            "total_score": total_score * 100,  # 0-100 scale
        }

    def _check_entity_presence(
        self, result: Dict[str, Any], expected_entity: Optional[str]
    ) -> float:
        """결과에 예상 엔티티가 포함되어 있는지 확인"""

        if not expected_entity:
            return 1.0  # 엔티티를 찾을 필요가 없으면 만점

        # 결과의 다양한 필드에서 엔티티 찾기
        search_fields = ["name", "title", "assignee", "member", "username", "user", "content"]
        for field in search_fields:
            if field in result and expected_entity in str(result[field]).lower():
                return 1.0

        return 0.3  # 엔티티 미발견 시 부분 점수

    def _calculate_semantic_similarity(self, result: Dict[str, Any], query: str) -> float:
        """쿼리와 결과의 의미적 유사도 계산 (임베딩 기반)
        """
        if not self.embedding_model:
            return 0.0

        try:
            # 쿼리 임베딩
            query_embedding = self.embedding_model.encode(query)

            # 결과 본문 임베딩 (그래프 맥락 우선)
            content = result.get("graph_context") or result.get("content", "")
            if not content:
                return 0.3  # 내용이 없으면 낮은 점수

            content_embedding = self.embedding_model.encode(content)

            # 코사인 유사도
            similarity = self._cosine_similarity(query_embedding, content_embedding)
            return float(similarity)
        except Exception as e:
            logger.warning(f"Semantic similarity calculation failed: {e}")
            return 0.0

    def _cosine_similarity(self, vec1, vec2) -> float:
        """코사인 유사도 계산"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def _calculate_recency(self, result: Dict[str, Any]) -> float:
        """문서의 최신성 계산

        최근 3개월: 1.0, 6개월: 0.7, 1년: 0.5, 그 외: 0.3
        """
        parsed_date = extract_date_from_result(result)
        if not parsed_date:
            return 0.5

        return calculate_recency_score(parsed_date)

    def _assess_quality(self, score: float, result_count: int) -> str:
        """점수 기반 품질 평가"""

        # 결과 개수 고려
        if result_count == 0:
            return "결과없음"
        elif result_count > 50:
            quality_threshold = 60  # 결과가 많으면 기준을 높임
        else:
            quality_threshold = 50

        if score >= 80:
            return "높음"
        elif score >= quality_threshold:
            return "중간"
        else:
            return "낮음"

