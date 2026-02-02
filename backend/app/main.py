import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.infrastructure.graph.checkpointer import close_checkpointer

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """애플리케이션 라이프사이클"""
    # 시작 시
    yield
    # 종료 시
    await engine.dispose()
    await close_checkpointer()  # LangGraph checkpointer 연결 정리


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Mit - Collaborative organization knowledge system API",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict:
    """헬스 체크"""
    return {"status": "ok"}
