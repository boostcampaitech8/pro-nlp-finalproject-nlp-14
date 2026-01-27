"""Docker Compose 기반 WorkerManager 구현

subprocess로 docker run 호출하여 워커 컨테이너 관리
K8s 환경에서는 kubernetes.py의 K8sWorkerManager가 사용됨
"""

import asyncio
import logging
import os
import re
from pathlib import Path

from .base import WorkerStartError, WorkerStatus, WorkerStatusEnum

logger = logging.getLogger(__name__)

# docker-compose.yml 위치 (backend 기준 상대 경로)
COMPOSE_FILE = Path(__file__).parent.parent.parent.parent.parent / "docker" / "docker-compose.yml"


class DockerWorkerManager:
    """Docker Compose 기반 워커 관리자"""

    def __init__(self, compose_file: Path | None = None):
        """
        Args:
            compose_file: docker-compose.yml 경로 (기본값: 프로젝트 docker/docker-compose.yml)
        """
        self.compose_file = compose_file or COMPOSE_FILE
        self._container_prefix = "realtime-worker"

    def _get_container_name(self, meeting_id: str) -> str:
        """meeting_id로 컨테이너 이름 생성"""
        # meeting_id에서 특수문자 제거
        safe_id = re.sub(r"[^a-zA-Z0-9-]", "", meeting_id)
        return f"{self._container_prefix}-{safe_id}"

    async def _run_docker_command(self, *args: str) -> tuple[int, str, str]:
        """docker 명령어 실행

        Returns:
            (return_code, stdout, stderr)
        """
        cmd = ["docker", *args]
        logger.debug(f"Docker 명령어 실행: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.compose_file.parent,  # docker-compose.yml 디렉토리에서 실행
        )
        stdout, stderr = await proc.communicate()

        return (
            proc.returncode or 0,
            stdout.decode().strip(),
            stderr.decode().strip(),
        )

    async def _load_env_vars(self) -> dict[str, str]:
        """.env 파일에서 환경변수 로드"""
        env_file = self.compose_file.parent / ".env"
        env_vars = {}

        if not env_file.exists():
            logger.warning(f".env 파일을 찾을 수 없음: {env_file}")
            return env_vars

        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    # 주석이나 빈 줄 제외
                    if not line or line.startswith("#"):
                        continue
                    # KEY=VALUE 파싱
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            logger.error(f".env 파일 로드 실패: {e}")

        return env_vars

    async def start_worker(self, meeting_id: str) -> str:
        """워커 컨테이너 시작

        docker compose run -d --name <name> -e MEETING_ID=<id> realtime-worker
        """
        container_name = self._get_container_name(meeting_id)

        # 이미 실행 중인지 확인
        existing = await self.get_status(container_name)
        if existing.status == WorkerStatusEnum.RUNNING:
            logger.warning(f"워커가 이미 실행 중: {container_name}")
            return container_name

        # 기존 컨테이너가 있으면 삭제
        if existing.status in (WorkerStatusEnum.STOPPED, WorkerStatusEnum.FAILED):
            await self._run_docker_command("rm", "-f", container_name)

        # 새 컨테이너 시작
        # docker run으로 직접 시작 (compose 사용 안함 - 전체 스택에 영향 없음)
        # 환경변수는 .env에서 읽어서 전달
        env_vars = await self._load_env_vars()

        docker_args = [
            "run",
            "-d",
            "--name",
            container_name,
            "--network",
            "mit-network",  # compose 네트워크 사용
            "-e",
            f"MEETING_ID={meeting_id}",
        ]

        # .env에서 필요한 환경변수 전달
        for key in ["LIVEKIT_WS_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
                    "CLOVA_STT_ENDPOINT", "CLOVA_STT_SECRET",
                    "BACKEND_API_URL", "BACKEND_API_KEY", "LOG_LEVEL"]:
            if key in env_vars:
                docker_args.extend(["-e", f"{key}={env_vars[key]}"])

        docker_args.append("docker-realtime-worker:latest")

        return_code, stdout, stderr = await self._run_docker_command(*docker_args)

        if return_code != 0:
            error_msg = f"워커 시작 실패: {stderr}"
            logger.error(error_msg)
            raise WorkerStartError(error_msg)

        logger.info(f"워커 시작됨: {container_name} (meeting={meeting_id})")
        return container_name

    async def stop_worker(self, worker_id: str) -> bool:
        """워커 컨테이너 종료

        docker stop <container_name>
        """
        return_code, _, stderr = await self._run_docker_command("stop", worker_id)

        if return_code != 0:
            logger.warning(f"워커 종료 실패: {stderr}")
            return False

        logger.info(f"워커 종료됨: {worker_id}")
        return True

    async def get_status(self, worker_id: str) -> WorkerStatus:
        """워커 상태 조회

        docker inspect --format '{{.State.Status}}' <container_name>
        """
        # meeting_id 추출 (container_name에서 prefix 제거)
        meeting_id = worker_id.replace(f"{self._container_prefix}-", "")

        return_code, stdout, _ = await self._run_docker_command(
            "inspect",
            "--format",
            "{{.State.Status}}|{{.State.ExitCode}}",
            worker_id,
        )

        if return_code != 0:
            return WorkerStatus(
                worker_id=worker_id,
                meeting_id=meeting_id,
                status=WorkerStatusEnum.NOT_FOUND,
            )

        parts = stdout.split("|")
        docker_status = parts[0] if parts else ""
        exit_code = int(parts[1]) if len(parts) > 1 else None

        # Docker 상태 -> WorkerStatusEnum 매핑
        status_map = {
            "created": WorkerStatusEnum.PENDING,
            "running": WorkerStatusEnum.RUNNING,
            "paused": WorkerStatusEnum.RUNNING,
            "restarting": WorkerStatusEnum.PENDING,
            "removing": WorkerStatusEnum.STOPPED,
            "exited": WorkerStatusEnum.STOPPED if exit_code == 0 else WorkerStatusEnum.FAILED,
            "dead": WorkerStatusEnum.FAILED,
        }

        status = status_map.get(docker_status, WorkerStatusEnum.NOT_FOUND)

        return WorkerStatus(
            worker_id=worker_id,
            meeting_id=meeting_id,
            status=status,
            exit_code=exit_code,
        )

    async def list_workers(self, meeting_id: str | None = None) -> list[WorkerStatus]:
        """실행 중인 워커 목록 조회

        docker ps --filter name=realtime-worker --format '{{.Names}}'
        """
        return_code, stdout, _ = await self._run_docker_command(
            "ps",
            "-a",  # 종료된 것도 포함
            "--filter",
            f"name={self._container_prefix}",
            "--format",
            "{{.Names}}",
        )

        if return_code != 0 or not stdout:
            return []

        container_names = stdout.split("\n")
        workers = []

        for name in container_names:
            if not name:
                continue

            status = await self.get_status(name)

            # meeting_id 필터링
            if meeting_id and status.meeting_id != meeting_id:
                continue

            workers.append(status)

        return workers

    async def cleanup_stopped_workers(self) -> int:
        """종료된 워커 컨테이너 정리

        Returns:
            삭제된 컨테이너 수
        """
        workers = await self.list_workers()
        removed = 0

        for worker in workers:
            if worker.status in (WorkerStatusEnum.STOPPED, WorkerStatusEnum.FAILED):
                return_code, _, _ = await self._run_docker_command("rm", worker.worker_id)
                if return_code == 0:
                    removed += 1
                    logger.info(f"워커 컨테이너 삭제됨: {worker.worker_id}")

        return removed
