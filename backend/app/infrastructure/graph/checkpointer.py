"""LangGraph Checkpointer 관리 (AsyncPostgresSaver 기반)

멀티턴 대화 상태 영속화를 위한 checkpointer 싱글톤 관리.
SQLAlchemy와 별도의 psycopg 연결 풀 사용.

사용 예시:
    from app.infrastructure.graph.checkpointer import get_checkpointer

    checkpointer = await get_checkpointer()
    graph = workflow.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": meeting_id}}
    result = await graph.ainvoke(state, config)
"""

import asyncio
import logging
from contextlib import AsyncExitStack

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 모듈 레벨 싱글톤 (lazy initialization)
_checkpointer: AsyncPostgresSaver | None = None
_exit_stack: AsyncExitStack | None = None
_lock = asyncio.Lock()


async def get_checkpointer() -> AsyncPostgresSaver:
    """Checkpointer 싱글톤 반환 (lazy initialization)

    첫 호출 시 연결 풀 생성 및 스키마 초기화.
    워커 재시작 시 자동 복구.

    Returns:
        AsyncPostgresSaver: LangGraph 상태 영속화용 checkpointer

    Note:
        - setup()은 idempotent하게 테이블 생성
        - 생성되는 테이블: checkpoints, checkpoint_blobs, checkpoint_writes
    """
    global _checkpointer, _exit_stack

    if _checkpointer is None:
        async with _lock:
            if _checkpointer is None:
                settings = get_settings()

                # AsyncExitStack으로 context manager 관리
                _exit_stack = AsyncExitStack()

                # from_conn_string은 async context manager 반환
                # TCP keepalive로 stale 커넥션 감지 및 자동 정리
                _checkpointer = await _exit_stack.enter_async_context(
                    AsyncPostgresSaver.from_conn_string(
                        settings.checkpointer_database_url,
                        pool_kwargs={
                            "max_size": 10,
                            "kwargs": {
                                "keepalives": 1,
                                "keepalives_idle": 30,
                                "keepalives_interval": 10,
                                "keepalives_count": 5,
                            },
                        },
                    )
                )

                # 스키마 초기화 (idempotent - 이미 존재하면 무시)
                await _checkpointer.setup()
                logger.info("AsyncPostgresSaver initialized with PostgreSQL")

    return _checkpointer


async def close_checkpointer() -> None:
    """애플리케이션 종료 시 연결 정리

    FastAPI lifespan 종료 시 호출되어야 함.
    """
    global _checkpointer, _exit_stack

    if _exit_stack is not None:
        await _exit_stack.aclose()
        _exit_stack = None
        _checkpointer = None
        logger.info("AsyncPostgresSaver connection closed")
