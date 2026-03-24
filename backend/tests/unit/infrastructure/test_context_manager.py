"""ContextManager unit tests."""

from datetime import datetime, timezone

from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.manager import ContextManager
from app.infrastructure.context.models import Utterance


def _utt(idx: int) -> Utterance:
    return Utterance(
        id=idx,
        speaker_id=f"u-{idx}",
        speaker_name=f"User{idx}",
        text=f"text-{idx}",
        start_ms=idx * 1000,
        end_ms=idx * 1000 + 500,
        confidence=0.9,
        absolute_timestamp=datetime.now(timezone.utc),
    )


def test_get_utterances_in_range_reads_from_memory_buffers():
    """메모리 버퍼에서 범위 발화를 조회한다."""
    manager = ContextManager(
        meeting_id="meeting-1",
        config=ContextConfig(),
    )

    for i in range(1, 6):
        manager.l0_buffer.append(_utt(i))

    manager.l0_topic_buffer.append(_utt(3))
    manager.l0_topic_buffer.append(_utt(6))

    result = manager.get_utterances_in_range(2, 4)

    assert [u.id for u in result] == [2, 3, 4]


def test_get_utterances_in_range_returns_empty_for_invalid_range():
    """start > end 인 경우 빈 리스트를 반환한다."""
    manager = ContextManager(meeting_id="meeting-1", config=ContextConfig())

    assert manager.get_utterances_in_range(10, 1) == []
