"""SpeakerContext - 화자별 컨텍스트 관리

다자간 회의에서 화자 구분 및 역할 추론
"""

from collections import deque
from typing import Literal

from pydantic import BaseModel

from app.infrastructure.context.models import Utterance


class SpeakerStats(BaseModel):
    """화자별 통계"""

    user_id: str
    name: str
    utterance_count: int = 0
    question_count: int = 0
    statement_count: int = 0
    total_words: int = 0
    avg_utterance_length: float = 0.0


SpeakerRole = Literal["facilitator", "presenter", "participant", "observer"]


class SpeakerContext:
    """화자별 컨텍스트 관리

    다자간 회의에서:
    - 화자별 발화 버퍼 관리
    - 화자간 상호작용 패턴 추적
    - 역할 추론 (facilitator, presenter, participant)
    """

    def __init__(self, max_buffer_per_speaker: int = 25):
        self.max_buffer = max_buffer_per_speaker

        # 화자별 발화 버퍼
        self.speaker_buffers: dict[str, deque[Utterance]] = {}

        # 화자 역할 추론 결과
        self.speaker_roles: dict[str, SpeakerRole] = {}

        # 화자간 상호작용 매트릭스 (who responds to whom)
        self.interaction_matrix: dict[tuple[str, str], int] = {}

        # 화자별 통계
        self.speaker_stats: dict[str, SpeakerStats] = {}

        # 마지막 발화자 (상호작용 추적용)
        self._last_speaker_id: str | None = None

    def add_utterance(self, utterance: Utterance) -> None:
        """발화 추가 및 통계 업데이트

        Args:
            utterance: 발화 데이터
        """
        speaker_id = utterance.speaker_id

        # 버퍼 초기화
        if speaker_id not in self.speaker_buffers:
            self.speaker_buffers[speaker_id] = deque(maxlen=self.max_buffer)
            self.speaker_stats[speaker_id] = SpeakerStats(
                user_id=speaker_id,
                name=utterance.speaker_name,
            )

        # 버퍼에 추가
        self.speaker_buffers[speaker_id].append(utterance)

        # 통계 업데이트
        stats = self.speaker_stats[speaker_id]
        stats.utterance_count += 1
        words = len(utterance.text.split())
        stats.total_words += words
        stats.avg_utterance_length = stats.total_words / stats.utterance_count

        # 질문 여부 판단 (한국어 휴리스틱)
        if self._is_question(utterance.text):
            stats.question_count += 1
        else:
            stats.statement_count += 1

        # 상호작용 매트릭스 업데이트
        if self._last_speaker_id and self._last_speaker_id != speaker_id:
            key = (self._last_speaker_id, speaker_id)
            self.interaction_matrix[key] = self.interaction_matrix.get(key, 0) + 1

        self._last_speaker_id = speaker_id

    def _is_question(self, text: str) -> bool:
        """질문 여부 판단

        Args:
            text: 발화 텍스트

        Returns:
            bool: 질문 여부
        """
        question_endings = ["?", "까요", "나요", "습니까", "ㅂ니까", "을까", "ㄹ까", "지요", "죠"]
        question_starters = ["어떻게", "왜", "누가", "언제", "어디", "무엇", "뭐", "어느"]

        # 물음표 체크
        if "?" in text:
            return True

        # 질문형 어미 체크
        for ending in question_endings:
            if text.endswith(ending):
                return True

        # 질문 시작어 체크
        for starter in question_starters:
            if text.startswith(starter):
                return True

        return False

    def infer_roles(self) -> dict[str, SpeakerRole]:
        """발화 패턴에서 역할 추론

        - 질문을 많이 하는 사람 -> facilitator (의사결정자/리더)
        - 설명을 많이 하는 사람 -> presenter (담당자/전문가)
        - 기타 -> participant

        Returns:
            dict: user_id -> role 매핑
        """
        roles: dict[str, SpeakerRole] = {}

        if not self.speaker_stats:
            return roles

        # 통계 기반 역할 추론
        for user_id, stats in self.speaker_stats.items():
            if stats.utterance_count == 0:
                continue

            question_ratio = stats.question_count / stats.utterance_count

            # 질문 비율이 높으면 facilitator
            if question_ratio > 0.5:
                roles[user_id] = "facilitator"
            # 발화량이 많고 질문 비율이 낮으면 presenter
            elif stats.avg_utterance_length > 20:
                roles[user_id] = "presenter"
            # 발화가 거의 없으면 observer
            elif stats.utterance_count < 3:
                roles[user_id] = "observer"
            else:
                roles[user_id] = "participant"

        self.speaker_roles = roles
        return roles

    def get_speaker_utterances(
        self,
        speaker_id: str,
        limit: int | None = None,
    ) -> list[Utterance]:
        """특정 화자의 발화 목록 반환

        Args:
            speaker_id: 화자 ID
            limit: 반환할 최대 발화 수

        Returns:
            list: 발화 목록
        """
        if speaker_id not in self.speaker_buffers:
            return []

        utterances = list(self.speaker_buffers[speaker_id])
        if limit:
            return utterances[-limit:]
        return utterances

    def get_all_speakers(self) -> list[str]:
        """모든 화자 ID 반환"""
        return list(self.speaker_buffers.keys())

    def get_speaker_stats(self, speaker_id: str) -> SpeakerStats | None:
        """화자 통계 반환

        Args:
            speaker_id: 화자 ID

        Returns:
            SpeakerStats | None: 화자 통계 (없으면 None)
        """
        return self.speaker_stats.get(speaker_id)

    def get_interaction_summary(self) -> dict[str, list[str]]:
        """화자간 상호작용 요약

        Returns:
            dict: speaker_id -> 자주 응답하는 상대방 목록
        """
        summary: dict[str, list[str]] = {}

        for (from_speaker, to_speaker), count in self.interaction_matrix.items():
            if from_speaker not in summary:
                summary[from_speaker] = []
            if count >= 2:  # 2회 이상 응답한 경우만 포함
                summary[from_speaker].append(to_speaker)

        return summary

    def format_attribution(self, utterances: list[Utterance]) -> str:
        """발화 어트리뷰션 포맷팅

        에이전트 응답에 사용할 발화 출처 포맷

        Args:
            utterances: 발화 목록

        Returns:
            str: 포맷팅된 발화 출처
        """
        lines = []
        for u in utterances:
            ts = u.absolute_timestamp.strftime("%H:%M")
            lines.append(f"- **{u.speaker_name}** ({ts}): \"{u.text}\"")
        return "\n".join(lines)

    def reset(self) -> None:
        """상태 초기화"""
        self.speaker_buffers.clear()
        self.speaker_roles.clear()
        self.interaction_matrix.clear()
        self.speaker_stats.clear()
        self._last_speaker_id = None
