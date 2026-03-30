from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.worker_manager import WorkerStatusEnum
from app.workers.arq_worker import cleanup_realtime_worker_task


@pytest.mark.asyncio
async def test_cleanup_realtime_worker_task_retries_and_succeeds():
    """삭제 실패 후 재시도에서 성공하면 success를 반환한다."""
    mock_worker_manager = MagicMock()
    mock_worker_manager.stop_worker = AsyncMock(side_effect=[False, True])
    mock_worker_manager.get_status = AsyncMock(
        return_value=MagicMock(status=WorkerStatusEnum.RUNNING)
    )

    with patch(
        "app.infrastructure.worker_manager.get_worker_manager",
        return_value=mock_worker_manager,
    ):
        with patch("app.workers.arq_worker.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            result = await cleanup_realtime_worker_task.__wrapped__(
                {}, "meeting-1", "realtime-worker-meeting-1", "stop_worker_failed", 3
            )

    assert result["status"] == "success"
    assert result["attempt"] == 2
    assert mock_worker_manager.stop_worker.await_count == 2
    mock_sleep.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_cleanup_realtime_worker_task_falls_back_to_ttl():
    """재시도 소진 시 ttl_fallback 상태를 반환한다."""
    mock_worker_manager = MagicMock()
    mock_worker_manager.stop_worker = AsyncMock(return_value=False)
    mock_worker_manager.get_status = AsyncMock(
        return_value=MagicMock(status=WorkerStatusEnum.RUNNING)
    )

    with patch(
        "app.infrastructure.worker_manager.get_worker_manager",
        return_value=mock_worker_manager,
    ):
        with patch("app.workers.arq_worker.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            result = await cleanup_realtime_worker_task.__wrapped__(
                {}, "meeting-1", "realtime-worker-meeting-1", "stop_worker_failed", 2
            )

    assert result["status"] == "ttl_fallback"
    assert result["attempts"] == 2
    assert mock_worker_manager.stop_worker.await_count == 2
    mock_sleep.assert_awaited_once_with(5)
