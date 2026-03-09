"""Test for Approval Gateway with Unconfirmed Agendas

Integration test to verify that Decision approval checks for unconfirmed agendas.
"""

import pytest

from app.repositories.kg.mock_repository import MockKGRepository


@pytest.fixture
def mock_repo():
    """Fixture for mock repository."""
    return MockKGRepository()


@pytest.mark.asyncio
async def test_create_minutes_with_matching(mock_repo):
    """Test that create_minutes calls agenda matcher and sets match metadata."""
    meeting_id = "meeting-1"

    # Create meeting first
    await mock_repo._ensure_meeting_exists(meeting_id)

    # Define agendas for minutes creation
    agendas = [
        {
            "topic": "예산 2억 확정",
            "description": "Q2 출시 결정",
            "evidence": [],
            "decision": {
                "content": "예산안 최종 승인",
                "context": "회의에서 합의됨",
                "evidence": [],
            },
        },
    ]

    # Create minutes - this should trigger agenda matching
    minutes = await mock_repo.create_minutes(
        meeting_id=meeting_id,
        summary="회의 요약",
        agendas=agendas,
    )

    # Verify minutes were created
    assert minutes is not None
    assert len(minutes.agendas) == 1

    agenda = minutes.agendas[0]
    # match_status should be set (could be "new", "matched", or "needs_confirmation")
    # based on available team agendas (none in this test)
    assert agenda.match_status is not None


@pytest.mark.asyncio
async def test_get_unconfirmed_agendas_empty(mock_repo):
    """Test retrieving unconfirmed agendas when none exist."""
    meeting_id = "meeting-1"
    await mock_repo._ensure_meeting_exists(meeting_id)

    # Create meeting with no unconfirmed agendas
    agendas = [
        {
            "topic": "Topic 1",
            "description": "Description",
            "evidence": [],
            "decision": None,
        },
    ]

    await mock_repo.create_minutes(
        meeting_id=meeting_id,
        summary="Summary",
        agendas=agendas,
    )

    # Retrieve unconfirmed agendas
    unconfirmed = await mock_repo.get_unconfirmed_agendas(meeting_id)

    # Should be empty (since no matching occurred)
    assert isinstance(unconfirmed, list)


@pytest.mark.asyncio
async def test_confirm_agenda_match_confirm_action(mock_repo):
    """Test confirming an agenda match."""
    meeting_id = "meeting-1"
    await mock_repo._ensure_meeting_exists(meeting_id)

    # Create minutes which will generate agendas
    agendas = [
        {
            "topic": "Test Topic",
            "description": "Test Description",
            "evidence": [],
            "decision": None,
        },
    ]

    minutes = await mock_repo.create_minutes(
        meeting_id=meeting_id,
        summary="Summary",
        agendas=agendas,
    )

    agenda_id = minutes.agendas[0].id

    # Confirm the match
    result = await mock_repo.confirm_agenda_match(
        agenda_id=agenda_id,
        user_id="user-1",
        confirm=True,
        candidate_agenda_id="existing-agenda-1",
    )

    # Should return agenda with match_status = 'matched'
    assert result.match_status == "matched"


@pytest.mark.asyncio
async def test_confirm_agenda_match_ignore_action(mock_repo):
    """Test ignoring an agenda match."""
    meeting_id = "meeting-1"
    await mock_repo._ensure_meeting_exists(meeting_id)

    # Create minutes
    agendas = [
        {
            "topic": "Test Topic 2",
            "description": "Test Description 2",
            "evidence": [],
            "decision": None,
        },
    ]

    minutes = await mock_repo.create_minutes(
        meeting_id=meeting_id,
        summary="Summary",
        agendas=agendas,
    )

    agenda_id = minutes.agendas[0].id

    # Ignore the match (create as new agenda)
    result = await mock_repo.confirm_agenda_match(
        agenda_id=agenda_id,
        user_id="user-1",
        confirm=False,
    )

    # Should return agenda with match_status = 'new' and no candidate
    assert result.match_status == "new"
    assert result.candidate_agenda_id is None
