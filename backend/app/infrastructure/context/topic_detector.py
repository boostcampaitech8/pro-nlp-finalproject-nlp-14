"""TopicDetector - 토픽 변경 감지

두 가지 감지 전략:
1. 키워드 기반 빠른 감지 (LLM 호출 없음)
2. LLM 기반 정밀 감지 (필요시)
"""

import json
import logging

from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.models import Utterance
from app.infrastructure.context.prompts.topic_detection import (
    TOPIC_CHANGE_KEYWORDS,
    TOPIC_DETECTION_PROMPT,
)

logger = logging.getLogger(__name__)


class TopicChangeResult(BaseModel):
    """토픽 변경 감지 결과"""

    topic_changed: bool
    previous_topic: str | None = None
    current_topic: str | None = None
    confidence: float = 0.0
    reason: str = ""


class TopicDetector:
    """토픽 변경 감지기

    LLM 호출을 최소화하면서 정확한 토픽 전환을 감지
    """

    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()
        self._keywords = TOPIC_CHANGE_KEYWORDS
        self._llm_enabled = bool(get_settings().ncp_clovastudio_api_key)

    def quick_check(self, utterance: str) -> bool:
        """키워드 기반 빠른 토픽 전환 감지

        LLM 호출 없이 키워드만으로 판단.
        True 반환 시 LLM 정밀 검사 권장.

        Args:
            utterance: 발화 텍스트

        Returns:
            bool: 토픽 전환 가능성 여부
        """
        return any(kw in utterance for kw in self._keywords)

    async def detect(
        self,
        recent_utterances: list[Utterance],
        previous_topic_summary: str = "",
    ) -> TopicChangeResult:
        """LLM 기반 정밀 토픽 변경 감지

        Args:
            recent_utterances: 최근 발화 목록 (5턴 권장)
            previous_topic_summary: 이전 토픽 요약

        Returns:
            TopicChangeResult: 토픽 변경 감지 결과
        """
        if not recent_utterances:
            return TopicChangeResult(
                topic_changed=False,
                reason="no_utterances",
            )

        # 발화를 텍스트로 포맷팅
        utterances_text = "\n".join(
            f"[{u.speaker_name}] {u.text}" for u in recent_utterances
        )

        prompt = TOPIC_DETECTION_PROMPT.format(
            previous_topic_summary=previous_topic_summary or "(첫 토픽)",
            recent_utterances=utterances_text,
        )

        logger.debug(f"Topic detection requested for {len(recent_utterances)} utterances")

        # LLM 호출 시도
        llm_response = await self._call_llm(prompt)
        if llm_response:
            parsed = self._parse_llm_response(llm_response)
            if parsed:
                return parsed

        # 키워드 기반 폴백
        latest_text = recent_utterances[-1].text if recent_utterances else ""
        has_keyword = self.quick_check(latest_text)

        return TopicChangeResult(
            topic_changed=has_keyword,
            previous_topic=None,
            current_topic=None,
            confidence=0.5 if has_keyword else 0.0,
            reason="keyword_match" if has_keyword else "no_change_detected",
        )

    def _parse_llm_response(self, response: str) -> TopicChangeResult | None:
        """LLM 응답 파싱

        Args:
            response: LLM 응답 텍스트 (JSON 형태)

        Returns:
            TopicChangeResult: 파싱된 결과
        """
        data = self._safe_json_loads(response)
        if not data:
            logger.warning("Failed to parse LLM response for topic detection")
            return None

        return TopicChangeResult(
            topic_changed=bool(data.get("topic_changed", False)),
            previous_topic=data.get("previous_topic"),
            current_topic=data.get("current_topic"),
            confidence=float(data.get("confidence", 0.0)),
            reason=data.get("reason", ""),
        )

    def add_custom_keywords(self, keywords: list[str]) -> None:
        """커스텀 키워드 추가

        Args:
            keywords: 추가할 키워드 목록
        """
        self._keywords = list(set(self._keywords + keywords))

    def get_keywords(self) -> list[str]:
        """현재 키워드 목록 반환"""
        return self._keywords.copy()

    async def _call_llm(self, prompt: str) -> str | None:
        """LLM 호출 (실패 시 None 반환)"""
        if not self._llm_enabled:
            return None

        try:
            from app.infrastructure.graph.integration.llm import get_base_llm
        except Exception as e:
            logger.debug(f"Failed to import LLM client: {e}")
            return None

        try:
            llm = get_base_llm()
            response = await llm.ainvoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning(f"Topic detection LLM call failed: {e}")
            return None

    @staticmethod
    def _safe_json_loads(text: str) -> dict | None:
        """LLM 응답에서 JSON 파싱 (부분 추출 지원)"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
        return None
