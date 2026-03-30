# ===================================
# Stage 1: 의존성 빌드 (캐시 레이어)
# ===================================
FROM python:3.12-slim AS builder

# uv 설치 (빠른 패키지 매니저)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 작업 디렉토리
WORKDIR /app

# 의존성 파일만 먼저 복사 (레이어 캐싱 최적화)
COPY pyproject.toml uv.lock ./

# 의존성 설치
# --no-dev: 개발 의존성 제외
# --frozen: lock 파일 재생성 안함 (재현성)
RUN uv sync --frozen --no-dev

# protobuf 컴파일용 소스 복사
COPY nest.proto ./

# protobuf 빌드 (Clova Speech gRPC)
RUN mkdir -p ./build && \
    uv run python -m grpc_tools.protoc \
    -I=. \
    --python_out=./build \
    --grpc_python_out=./build \
    nest.proto


# ===================================
# Stage 2: 최종 런타임 이미지 (최소화)
# ===================================
FROM python:3.12-slim AS runtime

# LiveKit SDK 네이티브 라이브러리 의존성 설치
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libffi8 \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 비root 유저 생성 (보안)
RUN useradd -m -u 1000 worker

WORKDIR /app

# Stage 1에서 설치된 의존성 복사
COPY --from=builder /app/.venv /app/.venv

# 소스 코드 복사
COPY src ./src

# protobuf 소스 복사 및 빌드
COPY nest.proto ./
RUN mkdir -p ./build && \
    /app/.venv/bin/python -m grpc_tools.protoc \
    -I=. \
    --python_out=./build \
    --grpc_python_out=./build \
    nest.proto

# Python 경로 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/build
ENV PATH="/app/.venv/bin:$PATH"

# 비root 유저로 실행
USER worker

# Health check (선택적)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# 실행
CMD ["python", "-m", "src.main"]
