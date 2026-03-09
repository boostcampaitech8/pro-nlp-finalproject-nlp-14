"""Hybrid Agenda Matcher - Semantic + Lexical Similarity

전 팀 회의에서 동일/유사 아젠다를 감지하여 자동으로 연결합니다.
기존 아젠다의 Decision 상태를 점진적으로 outdated로 전환합니다.

Hybrid matching approach:
- Semantic similarity (60%): embedding 기반 cosine similarity
- Lexical similarity (30%): token 기반 Jaccard 유사도
- Recency weight (10%): 최신 아젠다 선호도
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.infrastructure.context.embedding import TopicEmbedder

logger = logging.getLogger(__name__)

# Matching thresholds
SEMANTIC_THRESHOLD_HIGH = 0.75  # 높은 신뢰도: 자동 매칭
SEMANTIC_THRESHOLD_MEDIUM = 0.50  # 중간 신뢰도: 사용자 확인 필요
RECENCY_WINDOW_DAYS = 30  # 최근 이 기간 내 아젠다만 고려


@dataclass
class AgendaMatch:
    """아젠다 매칭 결과."""
    matched_agenda_id: str
    matched_agenda_topic: str
    matched_agenda_meeting_id: str
    match_score: float
    match_status: str  # "matched" | "needs_confirmation" | "new"


@dataclass
class AgendaInfo:
    """기존 아젠다 정보."""
    agenda_id: str
    topic: str
    description: str
    meeting_id: str
    created_at: datetime


class AgendaMatcher:
    """하이브리드 아젠다 매칭 엔진 (semantic + lexical + recency)."""

    def __init__(self):
        """AgendaMatcher 초기화."""
        self.embedder = TopicEmbedder()

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """텍스트를 토큰으로 분해.

        Args:
            text: 텍스트

        Returns:
            토큰 집합 (최소 2글자 이상)
        """
        if not text:
            return set()
        # 공백 기준 분해, 2글자 이상만 포함
        tokens = set(t.strip() for t in text.split() if len(t.strip()) >= 2)
        return tokens

    @staticmethod
    def _jaccard_similarity(text1: str, text2: str) -> float:
        """Jaccard 유사도 (lexical overlap).

        Args:
            text1: 첫 번째 텍스트
            text2: 두 번째 텍스트

        Returns:
            Jaccard 유사도 (0 ~ 1)
        """
        tokens1 = AgendaMatcher._tokenize(text1)
        tokens2 = AgendaMatcher._tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        if union == 0:
            return 0.0

        return intersection / union

    @staticmethod
    def _recency_weight(created_at: datetime) -> float:
        """최근성 가중치 (최근 30일 내 아젠다 선호).

        Args:
            created_at: 아젠다 생성 시간

        Returns:
            가중치 (0 ~ 1, 최근일수록 높음)
        """
        if not isinstance(created_at, datetime):
            return 0.5

        days_ago = (datetime.utcnow() - created_at).days

        if days_ago < 0:
            return 1.0  # 미래 시간은 최신으로 간주

        if days_ago > RECENCY_WINDOW_DAYS:
            return 0.1  # 30일 이상 과거는 낮은 가중치

        # 선형 감쇠: 30일 경과 시 0.1, 0일 시 1.0
        return 1.0 - (days_ago / RECENCY_WINDOW_DAYS) * 0.9

    async def compute_agenda_match(
        self,
        new_agenda_topic: str,
        new_agenda_description: str,
        team_agendas: list[AgendaInfo],
    ) -> Optional[AgendaMatch]:
        """새 아젠다와 팀 내 기존 아젠다 간 최적 매칭을 계산.

        Args:
            new_agenda_topic: 새 아젠다 주제
            new_agenda_description: 새 아젠다 설명
            team_agendas: 팀 내 기존 아젠다 목록

        Returns:
            AgendaMatch (최적 매칭 결과) 또는 None (매칭 실패)
        """
        if not team_agendas:
            return None

        if not self.embedder.is_available:
            logger.warning("Embedding service not available, using lexical matching only")
            return await self._match_lexical_only(
                new_agenda_topic,
                new_agenda_description,
                team_agendas,
            )

        # 새 아젠다 임베딩
        new_combined_text = f"{new_agenda_topic} {new_agenda_description}"
        new_embedding = await self.embedder.embed_text_async(new_combined_text)

        if new_embedding is None:
            logger.warning("Failed to embed new agenda, using lexical matching only")
            return await self._match_lexical_only(
                new_agenda_topic,
                new_agenda_description,
                team_agendas,
            )

        # 기존 아젠다 배치 임베딩
        existing_texts = [
            f"{a.topic} {a.description}"
            for a in team_agendas
        ]
        existing_embeddings = await self.embedder.embed_batch_async(existing_texts)

        # 각 기존 아젠다에 대해 하이브리드 스코어 계산
        matches = []

        for i, agenda in enumerate(team_agendas):
            # 1. Semantic similarity (60%)
            existing_embedding = existing_embeddings[i]
            semantic_score = TopicEmbedder.cosine_similarity(
                new_embedding, existing_embedding
            )
            semantic_score = max(0.0, semantic_score)  # 음수 스코어 제거

            # 2. Lexical similarity (30%)
            lexical_score = self._jaccard_similarity(
                new_combined_text,
                f"{agenda.topic} {agenda.description}",
            )

            # 3. Recency weight (10%)
            recency_score = self._recency_weight(agenda.created_at)

            # Hybrid score: weighted combination
            # semantic(60%) + lexical(30%) + recency_boost(10%)
            hybrid_score = (
                semantic_score * 0.60 +
                lexical_score * 0.30 +
                recency_score * 0.10
            )

            logger.debug(
                f"Agenda match: {agenda.topic[:30]} | "
                f"semantic={semantic_score:.3f}, lexical={lexical_score:.3f}, "
                f"recency={recency_score:.3f}, hybrid={hybrid_score:.3f}"
            )

            matches.append((agenda, hybrid_score))

        # 최고 스코어 아젠다 선택
        if not matches:
            return None

        best_agenda, best_score = max(matches, key=lambda x: x[1])

        # 스코어에 따라 매칭 상태 결정
        if best_score >= SEMANTIC_THRESHOLD_HIGH:
            match_status = "matched"
        elif best_score >= SEMANTIC_THRESHOLD_MEDIUM:
            match_status = "needs_confirmation"
        else:
            return None  # 스코어 너무 낮음, 매칭 불가

        logger.info(
            f"Matched agenda: {best_agenda.topic} (score={best_score:.3f}, "
            f"status={match_status})"
        )

        return AgendaMatch(
            matched_agenda_id=best_agenda.agenda_id,
            matched_agenda_topic=best_agenda.topic,
            matched_agenda_meeting_id=best_agenda.meeting_id,
            match_score=best_score,
            match_status=match_status,
        )

    async def _match_lexical_only(
        self,
        new_agenda_topic: str,
        new_agenda_description: str,
        team_agendas: list[AgendaInfo],
    ) -> Optional[AgendaMatch]:
        """Fallback: 어휘상 매칭만 사용.

        Args:
            new_agenda_topic: 새 아젠다 주제
            new_agenda_description: 새 아젠다 설명
            team_agendas: 팀 내 기존 아젠다 목록

        Returns:
            AgendaMatch (매칭 결과) 또는 None
        """
        new_combined = f"{new_agenda_topic} {new_agenda_description}"

        matches = []
        for agenda in team_agendas:
            lexical_score = self._jaccard_similarity(
                new_combined,
                f"{agenda.topic} {agenda.description}",
            )
            recency_score = self._recency_weight(agenda.created_at)

            # Lexical 매칭에서는 어휘 유사도에 더 높은 가중치
            hybrid_score = lexical_score * 0.80 + recency_score * 0.20

            logger.debug(
                f"Agenda lexical-only match: {agenda.topic[:30]} | "
                f"lexical={lexical_score:.3f}, recency={recency_score:.3f}, "
                f"hybrid={hybrid_score:.3f}"
            )

            matches.append((agenda, hybrid_score))

        if not matches:
            return None

        best_agenda, best_score = max(matches, key=lambda x: x[1])

        # Lexical 전용 매칭은 더 보수적인 임계값 사용
        if best_score >= 0.60:  # 어휘 일치도 60% 이상
            match_status = "matched"
        elif best_score >= 0.40:  # 40% 이상이면 확인 필요
            match_status = "needs_confirmation"
        else:
            return None

        logger.info(
            f"Lexical-only matched agenda: {best_agenda.topic} "
            f"(score={best_score:.3f}, status={match_status})"
        )

        return AgendaMatch(
            matched_agenda_id=best_agenda.agenda_id,
            matched_agenda_topic=best_agenda.topic,
            matched_agenda_meeting_id=best_agenda.meeting_id,
            match_score=best_score,
            match_status=match_status,
        )

    async def find_all_matches(
        self,
        new_agenda_topic: str,
        new_agenda_description: str,
        team_agendas: list[AgendaInfo],
        min_score: float = SEMANTIC_THRESHOLD_MEDIUM,
    ) -> list[tuple[AgendaInfo, float, str]]:
        """임계값 이상의 모든 매칭 후보 반환 (정렬됨).

        Args:
            new_agenda_topic: 새 아젠다 주제
            new_agenda_description: 새 아젠다 설명
            team_agendas: 팀 내 기존 아젠다 목록
            min_score: 최소 스코어 임계값

        Returns:
            (기존 아젠다, 스코어, 상태) 튜플 리스트 (스코어 내림차순)
        """
        if not team_agendas:
            return []

        # 위의 compute_agenda_match와 유사한 로직, 모든 후보 반환
        new_combined_text = f"{new_agenda_topic} {new_agenda_description}"
        matches = []

        if self.embedder.is_available:
            new_embedding = await self.embedder.embed_text_async(new_combined_text)
            if new_embedding is not None:
                existing_texts = [
                    f"{a.topic} {a.description}"
                    for a in team_agendas
                ]
                existing_embeddings = await self.embedder.embed_batch_async(existing_texts)

                for i, agenda in enumerate(team_agendas):
                    existing_embedding = existing_embeddings[i]
                    semantic_score = TopicEmbedder.cosine_similarity(
                        new_embedding, existing_embedding
                    )
                    semantic_score = max(0.0, semantic_score)

                    lexical_score = self._jaccard_similarity(
                        new_combined_text,
                        f"{agenda.topic} {agenda.description}",
                    )

                    recency_score = self._recency_weight(agenda.created_at)

                    hybrid_score = (
                        semantic_score * 0.60 +
                        lexical_score * 0.30 +
                        recency_score * 0.10
                    )

                    if hybrid_score >= min_score:
                        status = "matched" if hybrid_score >= SEMANTIC_THRESHOLD_HIGH else "needs_confirmation"
                        matches.append((agenda, hybrid_score, status))
            else:
                # Fallback to lexical
                for agenda in team_agendas:
                    lexical_score = self._jaccard_similarity(
                        new_combined_text,
                        f"{agenda.topic} {agenda.description}",
                    )
                    recency_score = self._recency_weight(agenda.created_at)
                    hybrid_score = lexical_score * 0.80 + recency_score * 0.20

                    if hybrid_score >= min_score:
                        status = "matched" if hybrid_score >= 0.60 else "needs_confirmation"
                        matches.append((agenda, hybrid_score, status))
        else:
            # Lexical only
            for agenda in team_agendas:
                lexical_score = self._jaccard_similarity(
                    new_combined_text,
                    f"{agenda.topic} {agenda.description}",
                )
                recency_score = self._recency_weight(agenda.created_at)
                hybrid_score = lexical_score * 0.80 + recency_score * 0.20

                if hybrid_score >= min_score:
                    status = "matched" if hybrid_score >= 0.60 else "needs_confirmation"
                    matches.append((agenda, hybrid_score, status))

        # 스코어 내림차순 정렬
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
