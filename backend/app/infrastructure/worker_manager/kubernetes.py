"""Kubernetes Job 기반 WorkerManager 구현

회의별 K8s Job을 동적으로 생성/삭제하여 워커 관리
DockerWorkerManager와 동일한 WorkerManager 프로토콜 준수
"""

import asyncio
import logging
import os
import re

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from .base import WorkerStartError, WorkerStatus, WorkerStatusEnum

logger = logging.getLogger(__name__)


class K8sWorkerManager:
    """Kubernetes Job 기반 워커 관리자

    회의 시작 시 K8s Job 생성, 종료 시 삭제
    in-cluster config로 자동 인증 (Pod 내부에서 실행)
    """

    def __init__(
        self,
        namespace: str | None = None,
        worker_image: str | None = None,
        image_pull_secret: str | None = None,
    ):
        """
        Args:
            namespace: K8s 네임스페이스 (기본값: KUBERNETES_NAMESPACE 환경변수 또는 'mit')
            worker_image: 워커 컨테이너 이미지 (기본값: WORKER_IMAGE 환경변수)
            image_pull_secret: Private 레지스트리 인증용 시크릿 (기본값: IMAGE_PULL_SECRET 환경변수)
        """
        # 로컬 개발 환경 지원: in-cluster 실패 시 kubeconfig 사용
        try:
            config.load_incluster_config()
            logger.info("K8s in-cluster config 로드 완료")
        except config.ConfigException:
            try:
                config.load_kube_config()
                logger.info("K8s kubeconfig 로드 완료 (로컬 개발 모드)")
            except config.ConfigException as e:
                raise RuntimeError("K8s config 로드 실패 (in-cluster, kubeconfig 모두 실패)") from e

        self.batch_v1 = client.BatchV1Api()
        self.core_v1 = client.CoreV1Api()
        self.namespace = namespace or os.getenv("KUBERNETES_NAMESPACE", "mit")
        self.worker_image = worker_image or os.getenv("WORKER_IMAGE") or self._get_default_worker_image()
        self.image_pull_secret = image_pull_secret or os.getenv("IMAGE_PULL_SECRET") or self._get_default_pull_secret()
        self._worker_prefix = "realtime-worker"

    def _is_running_in_k8s(self) -> bool:
        """현재 프로세스가 k8s Pod 내부에서 실행 중인지 확인"""
        return "KUBERNETES_SERVICE_HOST" in os.environ

    def _get_default_worker_image(self) -> str:
        """환경에 따른 기본 Worker 이미지"""
        if self._is_running_in_k8s():
            # k8s Pod: GHCR (ConfigMap에서 오버라이드됨)
            return "ghcr.io/teamatoi/mit-worker:latest"
        else:
            # 로컬 프로세스: k3d 로컬 레지스트리
            return "mit-registry:5000/mit-worker:latest"

    def _get_default_pull_secret(self) -> str:
        """환경에 따른 기본 imagePullSecret"""
        if self._is_running_in_k8s():
            # k8s Pod: GHCR 인증 필요
            return "ghcr-secret"
        else:
            # 로컬 프로세스: 로컬 레지스트리는 인증 불필요
            return ""

    def _get_job_name(self, meeting_id: str) -> str:
        """meeting_id로 Job 이름 생성"""
        safe_id = re.sub(r"[^a-zA-Z0-9-]", "", meeting_id)
        return f"{self._worker_prefix}-{safe_id}"

    def _extract_meeting_id(self, job_name: str) -> str:
        """Job 이름에서 meeting_id 추출"""
        return job_name.replace(f"{self._worker_prefix}-", "")

    def _get_backend_url(self) -> str:
        """백엔드 URL 자동 감지

        백엔드(현재 프로세스)가 어디서 실행되는지에 따라 워커가 사용할 URL 결정:
        - 백엔드가 k8s Pod에서 실행: backend:8000 (k8s Service)
        - 백엔드가 로컬에서 실행: host.docker.internal:8000 (호스트 접근)
        """
        if "KUBERNETES_SERVICE_HOST" in os.environ:
            return "http://backend:8000"
        else:
            return "http://host.docker.internal:8000"

    def _build_job(self, job_name: str, meeting_id: str, api_key_index: int) -> client.V1Job:
        """K8s Job 매니페스트 생성

        Args:
            job_name: Job 이름
            meeting_id: 회의 ID
            api_key_index: 할당된 Clova API 키 인덱스 (0-4)
        """
        return client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=self.namespace,
                labels={
                    "app": "realtime-worker",
                    "managed-by": "mit-backend",
                    "meeting-id": re.sub(r"[^a-zA-Z0-9._-]", "", meeting_id),
                    "clova-key-index": str(api_key_index),
                },
            ),
            spec=client.V1JobSpec(
                # 완료 후 5분 뒤 자동 삭제
                ttl_seconds_after_finished=300,
                # 재시도 없음 (실패 시 수동 확인)
                backoff_limit=0,
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            "app": "realtime-worker",
                            "meeting-id": re.sub(r"[^a-zA-Z0-9._-]", "", meeting_id),
                            "clova-key-index": str(api_key_index),
                        },
                    ),
                    spec=client.V1PodSpec(
                        image_pull_secrets=[
                            client.V1LocalObjectReference(name=self.image_pull_secret)
                        ] if self.image_pull_secret else None,
                        containers=[
                            client.V1Container(
                                name="worker",
                                image=self.worker_image,
                                image_pull_policy="Always",
                                env=[
                                    client.V1EnvVar(
                                        name="MEETING_ID",
                                        value=meeting_id,
                                    ),
                                    # 워커를 생성한 백엔드 URL 주입 (자동 감지)
                                    client.V1EnvVar(
                                        name="BACKEND_API_URL",
                                        value=self._get_backend_url(),
                                    ),
                                    # 할당된 Clova STT API 키 (Secret에서 참조)
                                    client.V1EnvVar(
                                        name="CLOVA_STT_SECRET",
                                        value_from=client.V1EnvVarSource(
                                            secret_key_ref=client.V1SecretKeySelector(
                                                name="mit-secrets",
                                                key=f"CLOVA_STT_SECRET_{api_key_index}",
                                            ),
                                        ),
                                    ),
                                ],
                                env_from=[
                                    client.V1EnvFromSource(
                                        config_map_ref=client.V1ConfigMapEnvSource(
                                            name="mit-config",
                                        ),
                                    ),
                                    client.V1EnvFromSource(
                                        secret_ref=client.V1SecretEnvSource(
                                            name="mit-secrets",
                                        ),
                                    ),
                                ],
                                resources=client.V1ResourceRequirements(
                                    requests={"memory": "128Mi", "cpu": "100m"},
                                    limits={"memory": "512Mi", "cpu": "500m"},
                                ),
                            ),
                        ],
                        restart_policy="Never",
                    ),
                ),
            ),
        )

    def _job_status_to_enum(self, job: client.V1Job) -> WorkerStatusEnum:
        """K8s Job 상태 -> WorkerStatusEnum 매핑"""
        status = job.status
        if status is None:
            return WorkerStatusEnum.PENDING

        # 완료 확인
        if status.succeeded and status.succeeded > 0:
            return WorkerStatusEnum.STOPPED
        if status.failed and status.failed > 0:
            return WorkerStatusEnum.FAILED

        # 활성 상태 확인
        if status.active and status.active > 0:
            return WorkerStatusEnum.RUNNING

        # 시작 대기 중
        return WorkerStatusEnum.PENDING

    async def start_worker(self, meeting_id: str) -> str:
        """K8s Job으로 워커 시작"""
        from app.services.clova_key_manager import get_clova_key_manager

        job_name = self._get_job_name(meeting_id)

        # 이미 실행 중인지 확인
        existing = await self.get_status(job_name)
        if existing.status == WorkerStatusEnum.RUNNING:
            logger.warning(f"워커가 이미 실행 중: {job_name}")
            return job_name

        # Clova API 키 할당
        key_manager = await get_clova_key_manager()
        api_key_index = await key_manager.allocate_key(meeting_id)
        if api_key_index is None:
            raise WorkerStartError("사용 가능한 Clova API 키가 없습니다")

        # 기존 Job이 있으면 삭제
        if existing.status in (WorkerStatusEnum.STOPPED, WorkerStatusEnum.FAILED,
                               WorkerStatusEnum.PENDING):
            await self._delete_job(job_name)

        # Job 생성 (할당된 키 인덱스 전달)
        job = self._build_job(job_name, meeting_id, api_key_index)
        try:
            await asyncio.to_thread(
                self.batch_v1.create_namespaced_job,
                namespace=self.namespace,
                body=job,
            )
        except ApiException as e:
            if e.status == 409:
                logger.info(f"워커 Job 이미 존재 (다른 인스턴스가 생성): {job_name}")
                return job_name
            # Job 생성 실패 시 키 반환
            await key_manager.release_key(meeting_id)
            error_msg = f"워커 Job 생성 실패: {e.reason} (status={e.status})"
            logger.error(error_msg)
            raise WorkerStartError(error_msg) from e

        logger.info(f"워커 Job 생성됨: {job_name} (meeting={meeting_id}, key_index={api_key_index})")
        return job_name

    async def stop_worker(self, worker_id: str) -> bool:
        """K8s Job 삭제로 워커 종료"""
        return await self._delete_job(worker_id)

    async def _delete_job(self, job_name: str) -> bool:
        """Job 및 관련 Pod 삭제"""
        try:
            # propagationPolicy=Background: Pod도 함께 삭제
            await asyncio.to_thread(
                self.batch_v1.delete_namespaced_job,
                name=job_name,
                namespace=self.namespace,
                propagation_policy="Background",
            )
            logger.info(f"워커 Job 삭제됨: {job_name}")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.debug(f"워커 Job 없음 (이미 삭제됨): {job_name}")
                return True
            logger.warning(f"워커 Job 삭제 실패: {e.reason}")
            return False

    async def get_status(self, worker_id: str) -> WorkerStatus:
        """K8s Job 상태 조회"""
        meeting_id = self._extract_meeting_id(worker_id)

        try:
            job = await asyncio.to_thread(
                self.batch_v1.read_namespaced_job,
                name=worker_id,
                namespace=self.namespace,
            )
        except ApiException as e:
            if e.status == 404:
                return WorkerStatus(
                    worker_id=worker_id,
                    meeting_id=meeting_id,
                    status=WorkerStatusEnum.NOT_FOUND,
                )
            logger.error(f"워커 상태 조회 실패: {e.reason}")
            return WorkerStatus(
                worker_id=worker_id,
                meeting_id=meeting_id,
                status=WorkerStatusEnum.NOT_FOUND,
            )

        status_enum = self._job_status_to_enum(job)

        # 실패 시 에러 메시지 추출
        error_message = None
        exit_code = None
        if status_enum == WorkerStatusEnum.FAILED:
            error_message = self._extract_error_from_job(job)
            exit_code = 1
        elif status_enum == WorkerStatusEnum.STOPPED:
            exit_code = 0

        return WorkerStatus(
            worker_id=worker_id,
            meeting_id=meeting_id,
            status=status_enum,
            exit_code=exit_code,
            error_message=error_message,
        )

    def _extract_error_from_job(self, job: client.V1Job) -> str | None:
        """Job 실패 시 에러 메시지 추출"""
        if job.status and job.status.conditions:
            for condition in job.status.conditions:
                if condition.type == "Failed":
                    return condition.message
        return None

    async def list_workers(self, meeting_id: str | None = None) -> list[WorkerStatus]:
        """실행 중인 워커 Job 목록 조회"""
        label_selector = "app=realtime-worker,managed-by=mit-backend"
        if meeting_id:
            safe_id = re.sub(r"[^a-zA-Z0-9._-]", "", meeting_id)
            label_selector += f",meeting-id={safe_id}"

        try:
            job_list = await asyncio.to_thread(
                self.batch_v1.list_namespaced_job,
                namespace=self.namespace,
                label_selector=label_selector,
            )
        except ApiException as e:
            logger.error(f"워커 목록 조회 실패: {e.reason}")
            return []

        workers = []
        for job in job_list.items:
            job_name = job.metadata.name
            m_id = self._extract_meeting_id(job_name)
            status_enum = self._job_status_to_enum(job)

            error_message = None
            exit_code = None
            if status_enum == WorkerStatusEnum.FAILED:
                error_message = self._extract_error_from_job(job)
                exit_code = 1
            elif status_enum == WorkerStatusEnum.STOPPED:
                exit_code = 0

            workers.append(
                WorkerStatus(
                    worker_id=job_name,
                    meeting_id=m_id,
                    status=status_enum,
                    exit_code=exit_code,
                    error_message=error_message,
                )
            )

        return workers

    async def cleanup_stopped_workers(self) -> int:
        """종료된 워커 Job 정리

        ttl_seconds_after_finished가 설정되어 있으므로
        K8s가 자동으로 정리하지만, 수동 정리도 가능
        """
        workers = await self.list_workers()
        removed = 0

        for worker in workers:
            if worker.status in (WorkerStatusEnum.STOPPED, WorkerStatusEnum.FAILED):
                if await self._delete_job(worker.worker_id):
                    removed += 1

        return removed
