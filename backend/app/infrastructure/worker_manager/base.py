"""WorkerManager 추상 인터페이스

Docker/K8s 구현체가 이 인터페이스를 따름
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class WorkerStatusEnum(str, Enum):
    """워커 상태"""

    PENDING = "pending"  # 생성 중
    RUNNING = "running"  # 실행 중
    STOPPED = "stopped"  # 정상 종료
    FAILED = "failed"  # 오류 종료
    NOT_FOUND = "not_found"  # 존재하지 않음


@dataclass
class WorkerStatus:
    """워커 상태 정보"""

    worker_id: str
    meeting_id: str
    status: WorkerStatusEnum
    exit_code: int | None = None  # 종료 시에만
    error_message: str | None = None  # 실패 시에만


class WorkerManager(Protocol):
    """워커 관리 인터페이스

    Docker/K8s 구현체가 이 프로토콜을 따름
    """

    async def start_worker(self, meeting_id: str) -> str:
        """워커 시작

        Args:
            meeting_id: 회의 ID

        Returns:
            worker_id: 생성된 워커 식별자

        Raises:
            WorkerStartError: 워커 시작 실패
        """
        ...

    async def stop_worker(self, worker_id: str) -> bool:
        """워커 종료

        Args:
            worker_id: 워커 식별자

        Returns:
            성공 여부
        """
        ...

    async def get_status(self, worker_id: str) -> WorkerStatus:
        """워커 상태 조회

        Args:
            worker_id: 워커 식별자

        Returns:
            워커 상태 정보
        """
        ...

    async def list_workers(self, meeting_id: str | None = None) -> list[WorkerStatus]:
        """워커 목록 조회

        Args:
            meeting_id: 필터링할 회의 ID (None이면 전체)

        Returns:
            워커 상태 목록
        """
        ...


class WorkerStartError(Exception):
    """워커 시작 실패 예외"""

    pass
