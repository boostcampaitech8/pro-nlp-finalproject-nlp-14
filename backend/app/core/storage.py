"""MinIO 객체 스토리지 서비스"""

import logging
from datetime import timedelta
from io import BytesIO
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """MinIO 스토리지 서비스"""

    BUCKET_RECORDINGS = "recordings"
    BUCKET_TRANSCRIPTS = "transcripts"

    def __init__(self):
        self._client: Minio | None = None

    def _get_client(self) -> Minio:
        """Lazy initialization of MinIO client"""
        if self._client is None:
            settings = get_settings()
            self._client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )
            self._ensure_buckets()
        return self._client

    def _ensure_buckets(self) -> None:
        """필요한 버킷 생성"""
        buckets = [self.BUCKET_RECORDINGS, self.BUCKET_TRANSCRIPTS]
        try:
            for bucket in buckets:
                if not self._client.bucket_exists(bucket):
                    self._client.make_bucket(bucket)
                    logger.info(f"Created bucket: {bucket}")
        except S3Error as e:
            logger.error(f"Failed to create bucket: {e}")
            raise

    def upload_file(
        self,
        bucket: str,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        """파일 업로드

        Args:
            bucket: 버킷 이름
            object_name: 객체 경로
            data: 파일 데이터 스트림
            length: 데이터 길이
            content_type: 콘텐츠 타입

        Returns:
            업로드된 객체 경로
        """
        client = self._get_client()
        try:
            client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type,
            )
            logger.info(f"Uploaded: {bucket}/{object_name}")
            return object_name
        except S3Error as e:
            logger.error(f"Upload failed: {e}")
            raise

    def upload_recording(
        self,
        meeting_id: str,
        user_id: str,
        timestamp: str,
        data: bytes,
    ) -> str:
        """녹음 파일 업로드

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            timestamp: 타임스탬프 (YYYYMMDD_HHMMSS)
            data: 오디오 데이터

        Returns:
            업로드된 파일 경로
        """
        object_name = f"{meeting_id}/{user_id}_{timestamp}.webm"
        data_stream = BytesIO(data)
        return self.upload_file(
            bucket=self.BUCKET_RECORDINGS,
            object_name=object_name,
            data=data_stream,
            length=len(data),
            content_type="audio/webm",
        )

    def upload_recording_file(
        self,
        meeting_id: str,
        user_id: str,
        timestamp: str,
        file_path: str,
    ) -> str:
        """녹음 파일 업로드 (파일 경로에서)

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            timestamp: 타임스탬프 (YYYYMMDD_HHMMSS)
            file_path: 로컬 파일 경로

        Returns:
            업로드된 파일 경로
        """
        client = self._get_client()
        object_name = f"{meeting_id}/{user_id}_{timestamp}.webm"

        try:
            client.fput_object(
                bucket_name=self.BUCKET_RECORDINGS,
                object_name=object_name,
                file_path=file_path,
                content_type="audio/webm",
            )
            logger.info(f"Uploaded file: {self.BUCKET_RECORDINGS}/{object_name}")
            return object_name
        except S3Error as e:
            logger.error(f"Upload file failed: {e}")
            raise

    def get_presigned_url(
        self,
        bucket: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Presigned URL 생성 (다운로드용)

        Args:
            bucket: 버킷 이름
            object_name: 객체 경로
            expires: URL 만료 시간

        Returns:
            Presigned URL (외부 접근용 URL로 변환됨)
        """
        client = self._get_client()
        settings = get_settings()
        try:
            url = client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expires,
            )
            # 내부 MinIO URL을 외부 프록시 URL로 변환
            # http://minio:9000/bucket/... -> https://domain.com/storage/bucket/...
            internal_url = f"http://{settings.minio_endpoint}"
            external_url = settings.storage_external_url
            return url.replace(internal_url, external_url)
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def get_presigned_upload_url(
        self,
        bucket: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Presigned URL 생성 (업로드용)

        Args:
            bucket: 버킷 이름
            object_name: 객체 경로
            expires: URL 만료 시간

        Returns:
            Presigned URL (외부 접근용 URL로 변환됨)
        """
        client = self._get_client()
        settings = get_settings()
        try:
            url = client.presigned_put_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expires,
            )
            # 내부 MinIO URL을 외부 프록시 URL로 변환
            # http://minio:9000/bucket/... -> https://domain.com/storage/bucket/...
            internal_url = f"http://{settings.minio_endpoint}"
            external_url = settings.storage_external_url
            return url.replace(internal_url, external_url)
        except S3Error as e:
            logger.error(f"Failed to generate presigned upload URL: {e}")
            raise

    def get_recording_upload_url(
        self,
        meeting_id: str,
        user_id: str,
        timestamp: str,
        expires: timedelta = timedelta(hours=1),
    ) -> tuple[str, str]:
        """녹음 파일 업로드 URL 생성

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            timestamp: 타임스탬프 (YYYYMMDD_HHMMSS)
            expires: URL 만료 시간

        Returns:
            (presigned_url, file_path) 튜플
        """
        file_path = f"{meeting_id}/{user_id}_{timestamp}.webm"
        url = self.get_presigned_upload_url(
            bucket=self.BUCKET_RECORDINGS,
            object_name=file_path,
            expires=expires,
        )
        return url, file_path

    def check_file_exists(self, bucket: str, object_name: str) -> bool:
        """파일 존재 여부 확인

        Args:
            bucket: 버킷 이름
            object_name: 객체 경로

        Returns:
            파일 존재 여부
        """
        client = self._get_client()
        try:
            client.stat_object(bucket_name=bucket, object_name=object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            logger.error(f"Failed to check file existence: {e}")
            raise

    def get_file_info(self, bucket: str, object_name: str) -> dict | None:
        """파일 정보 조회

        Args:
            bucket: 버킷 이름
            object_name: 객체 경로

        Returns:
            파일 정보 (size, content_type 등) 또는 None
        """
        client = self._get_client()
        try:
            stat = client.stat_object(bucket_name=bucket, object_name=object_name)
            return {
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
            }
        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            logger.error(f"Failed to get file info: {e}")
            raise

    def get_recording_url(
        self,
        file_path: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """녹음 파일 다운로드 URL 생성

        Args:
            file_path: 녹음 파일 경로
            expires: URL 만료 시간

        Returns:
            Presigned URL
        """
        return self.get_presigned_url(
            bucket=self.BUCKET_RECORDINGS,
            object_name=file_path,
            expires=expires,
        )

    def get_file(self, bucket: str, object_name: str) -> bytes:
        """파일 다운로드

        Args:
            bucket: 버킷 이름
            object_name: 객체 경로

        Returns:
            파일 데이터
        """
        client = self._get_client()
        try:
            response = client.get_object(bucket_name=bucket, object_name=object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.error(f"Download failed: {e}")
            raise

    def get_recording_file(self, file_path: str) -> bytes:
        """녹음 파일 다운로드

        Args:
            file_path: 녹음 파일 경로

        Returns:
            파일 데이터
        """
        return self.get_file(self.BUCKET_RECORDINGS, file_path)

    def check_recording_exists(self, file_path: str) -> bool:
        """녹음 파일 존재 여부 확인

        Args:
            file_path: 녹음 파일 경로

        Returns:
            파일 존재 여부
        """
        return self.check_file_exists(self.BUCKET_RECORDINGS, file_path)

    def get_recording_size(self, file_path: str) -> int:
        """녹음 파일 크기 조회

        Args:
            file_path: 녹음 파일 경로

        Returns:
            파일 크기 (bytes), 파일이 없으면 0
        """
        info = self.get_file_info(self.BUCKET_RECORDINGS, file_path)
        return info["size"] if info else 0

    def delete_file(self, bucket: str, object_name: str) -> None:
        """파일 삭제

        Args:
            bucket: 버킷 이름
            object_name: 객체 경로
        """
        client = self._get_client()
        try:
            client.remove_object(bucket, object_name)
            logger.info(f"Deleted: {bucket}/{object_name}")
        except S3Error as e:
            logger.error(f"Delete failed: {e}")
            raise

    def delete_recording(self, file_path: str) -> None:
        """녹음 파일 삭제

        Args:
            file_path: 녹음 파일 경로
        """
        self.delete_file(self.BUCKET_RECORDINGS, file_path)

    # === Transcript 관련 메서드 ===

    def upload_transcript(
        self,
        meeting_id: str,
        data: bytes,
        content_type: str = "application/json",
    ) -> str:
        """회의록 파일 업로드

        Args:
            meeting_id: 회의 ID
            data: 회의록 JSON 데이터
            content_type: 콘텐츠 타입

        Returns:
            업로드된 파일 경로
        """
        object_name = f"{meeting_id}/transcript.json"
        data_stream = BytesIO(data)
        return self.upload_file(
            bucket=self.BUCKET_TRANSCRIPTS,
            object_name=object_name,
            data=data_stream,
            length=len(data),
            content_type=content_type,
        )

    def get_transcript_url(
        self,
        file_path: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """회의록 파일 다운로드 URL 생성

        Args:
            file_path: 회의록 파일 경로
            expires: URL 만료 시간

        Returns:
            Presigned URL
        """
        return self.get_presigned_url(
            bucket=self.BUCKET_TRANSCRIPTS,
            object_name=file_path,
            expires=expires,
        )

    def get_transcript_file(self, file_path: str) -> bytes:
        """회의록 파일 다운로드

        Args:
            file_path: 회의록 파일 경로

        Returns:
            파일 데이터
        """
        return self.get_file(self.BUCKET_TRANSCRIPTS, file_path)

    def delete_transcript(self, file_path: str) -> None:
        """회의록 파일 삭제

        Args:
            file_path: 회의록 파일 경로
        """
        self.delete_file(self.BUCKET_TRANSCRIPTS, file_path)


# 싱글톤 인스턴스
storage_service = StorageService()
