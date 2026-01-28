from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# 비동기 엔진 생성
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    # 원격 DB 연결 안정화 설정 (VPN 환경 최적화)
    pool_pre_ping=True,  # 연결 재사용 전 테스트 (죽은 연결 감지)
    pool_recycle=300,    # 5분마다 연결 재활용 (VPN idle timeout 대응)
    pool_size=5,         # 기본 연결 풀 크기
    max_overflow=10,     # 최대 추가 연결 수
    pool_timeout=30,     # 연결 풀에서 연결 대기 타임아웃 (초)
    connect_args={
        "command_timeout": 60,  # 쿼리 타임아웃 60초
        "timeout": 10,  # asyncpg 연결/종료 타임아웃 (초)
        "server_settings": {
            "application_name": "mit-backend",
        },
    },
)

# 세션 팩토리
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """모든 모델의 기본 클래스"""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """DB 세션 의존성"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
