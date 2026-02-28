#!/usr/bin/env python3
"""MinIO에 업로드된 녹음 파일의 상태를 COMPLETED로 업데이트하는 스크립트

사용법:
    cd backend
    uv run python scripts/fix_recording_status.py

Docker 환경:
    docker exec -it mit-backend python scripts/fix_recording_status.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_engine, AsyncSessionLocal
from app.core.storage import storage_service
from app.models.recording import MeetingRecording, RecordingStatus

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def fix_recording_statuses():
    """MinIO에 파일이 존재하는 녹음의 상태를 COMPLETED로 업데이트"""

    async with AsyncSessionLocal() as db:
        # PENDING 또는 RECORDING 상태인 녹음 조회
        query = select(MeetingRecording).where(
            MeetingRecording.status.in_([
                RecordingStatus.PENDING.value,
                RecordingStatus.RECORDING.value,
            ])
        )
        result = await db.execute(query)
        recordings = result.scalars().all()

        logger.info(f"Found {len(recordings)} recordings to check")

        updated_count = 0
        not_found_count = 0

        for recording in recordings:
            logger.info(f"Checking recording {recording.id}: {recording.file_path}")

            try:
                # MinIO에서 파일 존재 여부 확인
                if storage_service.check_recording_exists(recording.file_path):
                    # 파일 크기 조회
                    file_size = storage_service.get_recording_size(recording.file_path)

                    # 상태 업데이트
                    recording.status = RecordingStatus.COMPLETED.value
                    recording.file_size_bytes = file_size

                    logger.info(f"  -> Updated to COMPLETED (size: {file_size} bytes)")
                    updated_count += 1
                else:
                    logger.warning(f"  -> File not found in MinIO: {recording.file_path}")
                    not_found_count += 1

            except Exception as e:
                logger.error(f"  -> Error checking file: {e}")

        if updated_count > 0:
            await db.commit()
            logger.info(f"Committed {updated_count} updates")

        logger.info(f"\nSummary:")
        logger.info(f"  - Total checked: {len(recordings)}")
        logger.info(f"  - Updated to COMPLETED: {updated_count}")
        logger.info(f"  - File not found: {not_found_count}")


async def list_all_recordings():
    """모든 녹음 상태 조회"""

    async with AsyncSessionLocal() as db:
        query = select(MeetingRecording).order_by(MeetingRecording.created_at.desc())
        result = await db.execute(query)
        recordings = result.scalars().all()

        logger.info(f"\n{'='*80}")
        logger.info(f"All Recordings ({len(recordings)} total)")
        logger.info(f"{'='*80}")

        for recording in recordings:
            logger.info(
                f"ID: {recording.id} | "
                f"Meeting: {recording.meeting_id} | "
                f"Status: {recording.status} | "
                f"Size: {recording.file_size_bytes or 0} bytes | "
                f"Path: {recording.file_path}"
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="녹음 상태 관리 스크립트")
    parser.add_argument("--list", action="store_true", help="모든 녹음 목록 조회")
    parser.add_argument("--fix", action="store_true", help="MinIO에 있는 녹음 상태 수정")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_all_recordings())
    elif args.fix:
        asyncio.run(fix_recording_statuses())
    else:
        # 기본: 둘 다 실행
        asyncio.run(list_all_recordings())
        asyncio.run(fix_recording_statuses())
