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
        try:
            if not self._client.bucket_exists(self.BUCKET_RECORDINGS):
                self._client.make_bucket(self.BUCKET_RECORDINGS)
                logger.info(f"Created bucket: {self.BUCKET_RECORDINGS}")
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
            Presigned URL
        """
        client = self._get_client()
        try:
            return client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expires,
            )
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
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


# 싱글톤 인스턴스
storage_service = StorageService()
