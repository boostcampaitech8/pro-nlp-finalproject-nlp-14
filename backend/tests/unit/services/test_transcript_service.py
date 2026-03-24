"""TranscriptService unit tests."""

import pytest

from app.models.transcript import Transcript
from app.services.transcript_service import TranscriptService


@pytest.mark.asyncio
async def test_get_utterances_by_range_returns_ordered_rows(db_session, test_meeting, test_user):
    """범위 내 발화를 start_ms 오름차순으로 반환한다."""
    service = TranscriptService(db_session)

    rows = [
        Transcript(
            meeting_id=test_meeting.id,
            user_id=test_user.id,
            start_ms=3000,
            end_ms=3500,
            transcript_text="세 번째",
            confidence=0.9,
            min_confidence=0.8,
            status="completed",
        ),
        Transcript(
            meeting_id=test_meeting.id,
            user_id=test_user.id,
            start_ms=1000,
            end_ms=1500,
            transcript_text="첫 번째",
            confidence=0.9,
            min_confidence=0.8,
            status="completed",
        ),
        Transcript(
            meeting_id=test_meeting.id,
            user_id=test_user.id,
            start_ms=2000,
            end_ms=2500,
            transcript_text="두 번째",
            confidence=0.9,
            min_confidence=0.8,
            status="completed",
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    utterances = await service.get_utterances_by_range(test_meeting.id, 0, 1)

    assert len(utterances) == 2
    assert utterances[0]["text"] == "첫 번째"
    assert utterances[1]["text"] == "두 번째"


@pytest.mark.asyncio
async def test_get_utterances_by_range_empty_for_invalid_range(db_session, test_meeting):
    """start > end 이면 빈 리스트를 반환한다."""
    service = TranscriptService(db_session)

    utterances = await service.get_utterances_by_range(test_meeting.id, 10, 1)

    assert utterances == []


@pytest.mark.asyncio
async def test_get_utterances_by_range_returns_empty_when_no_rows(db_session, test_meeting):
    """대상 회의에 발화가 없으면 빈 리스트를 반환한다."""
    service = TranscriptService(db_session)

    utterances = await service.get_utterances_by_range(test_meeting.id, 0, 5)

    assert utterances == []

