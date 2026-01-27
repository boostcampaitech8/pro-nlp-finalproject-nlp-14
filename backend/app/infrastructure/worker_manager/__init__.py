# worker_manager 패키지
import logging
import os

from .base import WorkerManager, WorkerStartError, WorkerStatus, WorkerStatusEnum

logger = logging.getLogger(__name__)

# 싱글톤 인스턴스
_worker_manager = None


def _is_kubernetes_env() -> bool:
    """K8s 환경인지 감지 (Pod 내부에서 자동 주입되는 환경변수 확인)"""
    return "KUBERNETES_SERVICE_HOST" in os.environ


def get_worker_manager() -> WorkerManager:
    """WorkerManager 싱글톤 반환

    K8s 환경이면 K8sWorkerManager, 아니면 DockerWorkerManager 반환
    """
    global _worker_manager
    if _worker_manager is not None:
        return _worker_manager

    if _is_kubernetes_env():
        from .kubernetes import K8sWorkerManager

        _worker_manager = K8sWorkerManager()
        logger.info("K8sWorkerManager 초기화 (K8s 환경 감지)")
    else:
        from .docker import DockerWorkerManager

        _worker_manager = DockerWorkerManager()
        logger.info("DockerWorkerManager 초기화 (Docker 환경)")

    return _worker_manager


__all__ = [
    "WorkerManager",
    "WorkerStatus",
    "WorkerStatusEnum",
    "WorkerStartError",
    "get_worker_manager",
]
