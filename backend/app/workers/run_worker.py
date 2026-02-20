"""ARQ Worker 실행 스크립트

Usage:
    cd backend
    uv run python -m app.workers.run_worker
"""

import logging

from arq import run_worker

from app.workers.arq_worker import WorkerSettings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
    run_worker(WorkerSettings)
