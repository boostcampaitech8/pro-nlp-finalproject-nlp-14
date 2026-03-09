"""의미론적 캐싱 시스템 - Semantic Cache Manager"""

import asyncio
import hashlib
import json
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheEntry:
    """캐시 항목"""

    def __init__(self, query: str, answer: str, embedding: list[float], confidence: float):
        self.query = query
        self.answer = answer
        self.embedding = embedding
        self.confidence = confidence
        self.created_at = datetime.now()
        self.access_count = 0
        self.last_accessed = datetime.now()

    def is_expired(self, ttl_hours: int = 24) -> bool:
        """캐시 만료 확인"""
        return datetime.now() - self.created_at > timedelta(hours=ttl_hours)

    def update_access(self):
        """접근 통계 업데이트"""
        self.access_count += 1
        self.last_accessed = datetime.now()


class SemanticCacheManager:
    """의미론적 캐시 관리자 (향후 Redis + Vector DB 연동)
    
    전략:
    1. 쿼리 임베딩 생성 (BGE)
    2. 벡터 DB에서 유사도 검색 (threshold > 0.9)
    3. 유사한 쿼리 발견 시 캐시된 답변 반환
    4. 캐시 미스 시 정상 처리 후 결과 캐시
    
    예상 효과:
    - 캐시 히트율: 20-30%
    - 히트 시 지연: 0.1s (50x 빠름)
    """

    def __init__(self):
        """캐시 관리자 초기화"""
        self.memory_cache: dict[str, CacheEntry] = {}
        self.total_hits = 0
        self.total_misses = 0

        # TODO: Redis 클라이언트 초기화
        # self.redis_client = redis.Redis(host='localhost', port=6379)

        # TODO: Vector DB 클라이언트 초기화
        # self.vector_db = VectorDatabase(host='localhost', port=19530)

    async def get_cached_answer(
        self,
        query: str,
        embedding: Optional[list[float]] = None,
        similarity_threshold: float = 0.9,
    ) -> Optional[dict[str, Any]]:
        """캐시에서 유사한 답변 조회

        Args:
            query: 사용자 쿼리
            embedding: 쿼리 임베딩 (None이면 생성)
            similarity_threshold: 유사도 임계값

        Returns:
            캐시된 결과 또는 None
        """
        logger.info(f"[Semantic Cache] 캐시 조회 중: {query[:50]}")

        try:
            # 1단계: 메모리 캐시에서 정확 매칭 확인
            cache_key = self._make_cache_key(query)
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if not entry.is_expired():
                    entry.update_access()
                    self.total_hits += 1
                    logger.info(
                        f"[Semantic Cache] 메모리 캐시 히트 "
                        f"(총 {self.total_hits}회)"
                    )
                    return {"answer": entry.answer, "source": "memory_cache"}

            # 2단계: 벡터 DB에서 의미론적 유사 검색
            # TODO: 실제 벡터 DB 연동
            # if embedding:
            #     similar_results = await self.vector_db.search(
            #         embedding=embedding,
            #         top_k=1,
            #         threshold=similarity_threshold
            #     )
            #     if similar_results:
            #         cached_entry = similar_results[0]
            #         if cached_entry["similarity"] > similarity_threshold:
            #             logger.info(
            #                 f"[Semantic Cache] 벡터 캐시 히트 "
            #                 f"(유사도: {cached_entry['similarity']:.2f})"
            #             )
            #             self.total_hits += 1
            #             return {
            #                 "answer": cached_entry["answer"],
            #                 "source": "vector_cache"
            #             }

            self.total_misses += 1
            logger.info(f"[Semantic Cache] 캐시 미스 (총 {self.total_misses}회)")
            return None

        except Exception as e:
            logger.error(f"[Semantic Cache] 캐시 조회 에러: {str(e)}", exc_info=True)
            return None

    async def cache_answer(
        self,
        query: str,
        answer: str,
        embedding: list[float],
        confidence: float = 0.95,
    ) -> None:
        """검색 결과를 캐시에 저장

        Args:
            query: 사용자 쿼리
            answer: 생성된 답변
            embedding: 쿼리 임베딩
            confidence: 답변 신뢰도
        """
        logger.info(f"[Semantic Cache] 캐시 저장 중: {query[:50]}")

        try:
            # 1단계: 메모리 캐시 저장
            cache_key = self._make_cache_key(query)
            entry = CacheEntry(query, answer, embedding, confidence)
            self.memory_cache[cache_key] = entry
            logger.info(f"[Semantic Cache] 메모리 캐시 저장 완료")

            # 2단계: 벡터 DB에 저장 (백그라운드)
            # TODO: 비동기 백그라운드로 벡터 DB 저장
            # await self.vector_db.insert({
            #     "query": query,
            #     "answer": answer,
            #     "embedding": embedding,
            #     "confidence": confidence,
            #     "timestamp": datetime.now()
            # })

        except Exception as e:
            logger.error(f"[Semantic Cache] 캐시 저장 에러: {str(e)}", exc_info=True)

    def clear_expired_cache(self, ttl_hours: int = 24) -> int:
        """만료된 캐시 삭제

        Args:
            ttl_hours: 캐시 유효 시간 (시간)

        Returns:
            삭제된 항목 수
        """
        expired_keys = [
            key
            for key, entry in self.memory_cache.items()
            if entry.is_expired(ttl_hours)
        ]

        for key in expired_keys:
            del self.memory_cache[key]

        if expired_keys:
            logger.info(f"[Semantic Cache] {len(expired_keys)}개 만료 캐시 삭제")

        return len(expired_keys)

    def get_cache_stats(self) -> dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.total_hits + self.total_misses
        hit_rate = (
            (self.total_hits / total_requests * 100)
            if total_requests > 0
            else 0.0
        )

        return {
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "total_requests": total_requests,
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_size": len(self.memory_cache),
            "memory_usage_mb": self._estimate_memory_usage(),
        }

    def _make_cache_key(self, query: str) -> str:
        """쿼리 해시로 캐시 키 생성"""
        return hashlib.md5(query.encode()).hexdigest()

    def _estimate_memory_usage(self) -> float:
        """메모리 사용량 추정 (MB)"""
        total_bytes = 0
        for entry in self.memory_cache.values():
            total_bytes += len(entry.query.encode())
            total_bytes += len(entry.answer.encode())
            total_bytes += len(entry.embedding) * 4  # float32
        return total_bytes / (1024 * 1024)


# 글로벌 캐시 인스턴스
_semantic_cache: Optional[SemanticCacheManager] = None


def get_semantic_cache() -> SemanticCacheManager:
    """글로벌 의미론적 캐시 인스턴스 반환"""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCacheManager()
    return _semantic_cache
