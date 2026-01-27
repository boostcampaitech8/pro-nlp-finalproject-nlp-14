#!/bin/bash
# 로컬 이미지 빌드 스크립트
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(cd "$K8S_DIR/.." && pwd)"

# 호스트에서 푸시: localhost:5111 (포트 매핑)
# 클러스터 내부 참조: mit-registry:5000 (Docker 네트워크)
# 둘 다 같은 레지스트리, 이미지 이름만 일치하면 됨
REGISTRY="localhost:5111"

echo "=== 이미지 빌드 ==="

# Backend
echo ">>> backend 빌드..."
docker build -t "$REGISTRY/mit-backend:latest" \
    -f "$PROJECT_ROOT/backend/Dockerfile" \
    "$PROJECT_ROOT/backend"
docker push "$REGISTRY/mit-backend:latest"

# Frontend
echo ">>> frontend 빌드..."
docker build -t "$REGISTRY/mit-frontend:latest" \
    --build-arg VITE_API_URL=/api/v1 \
    -f "$PROJECT_ROOT/frontend/Dockerfile" \
    "$PROJECT_ROOT"
docker push "$REGISTRY/mit-frontend:latest"

# Worker (있으면)
if [ -f "$PROJECT_ROOT/backend/worker/Dockerfile" ]; then
    echo ">>> worker 빌드..."
    docker build -t "$REGISTRY/mit-worker:latest" \
        -f "$PROJECT_ROOT/backend/worker/Dockerfile" \
        "$PROJECT_ROOT/backend/worker"
    docker push "$REGISTRY/mit-worker:latest"
fi

echo ""
echo "=== 빌드 완료 ==="
