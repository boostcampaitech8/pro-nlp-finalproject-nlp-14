#!/bin/bash
# 앱에서 사용하는 공통 Secret을 클러스터에 동기화
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$K8S_DIR")"

ENV="${1:-local}"
NAMESPACE="${KUBERNETES_NAMESPACE:-mit}"
SECRET_NAME="mit-secrets"

# .env 로드 (있으면 사용)
ENV_FILE="$ROOT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

if [ "$ENV" != "local" ]; then
    echo "❌ sync-app-secret.sh는 local 환경 전용입니다." >&2
    echo "   prod는 ESO/ExternalSecret로 Secret을 관리하세요." >&2
    exit 1
fi

# 로컬 개발 기본값
DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://mit:mitpassword@localhost:5432/mit}"
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-mitpassword}"
JWT_SECRET_KEY="${JWT_SECRET_KEY:-${JWT_SECRET:-change-this-secret-key}}"
# values/local.yaml.gotmpl의 livekit.apiKey와 반드시 동일해야 함
LIVEKIT_API_KEY="mit-api-key"
LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-secret-change-in-production-min-32-chars}"
CLOVA_ROUTER_ID="${CLOVA_ROUTER_ID:-}"
CLOVA_ROUTER_VERSION="${CLOVA_ROUTER_VERSION:-1}"
LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-https://cloud.langfuse.com}"
LANGFUSE_TRACING_ENABLED="${LANGFUSE_TRACING_ENABLED:-true}"
GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl create secret generic "$SECRET_NAME" -n "$NAMESPACE" \
    --from-literal=DATABASE_URL="${DATABASE_URL:-}" \
    --from-literal=NEO4J_URI="${NEO4J_URI:-}" \
    --from-literal=JWT_SECRET_KEY="${JWT_SECRET_KEY:-}" \
    --from-literal=keys.yaml="${LIVEKIT_API_KEY:-}: ${LIVEKIT_API_SECRET:-}" \
    --from-literal=LIVEKIT_API_KEY="${LIVEKIT_API_KEY:-}" \
    --from-literal=LIVEKIT_API_SECRET="${LIVEKIT_API_SECRET:-}" \
    --from-literal=NEO4J_USER="${NEO4J_USER:-neo4j}" \
    --from-literal=NEO4J_PASSWORD="${NEO4J_PASSWORD:-}" \
    --from-literal=GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}" \
    --from-literal=GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}" \
    --from-literal=CLOVA_STT_SECRET_0="${CLOVA_STT_SECRET_0:-}" \
    --from-literal=CLOVA_STT_SECRET_1="${CLOVA_STT_SECRET_1:-}" \
    --from-literal=CLOVA_STT_SECRET_2="${CLOVA_STT_SECRET_2:-}" \
    --from-literal=CLOVA_STT_SECRET_3="${CLOVA_STT_SECRET_3:-}" \
    --from-literal=CLOVA_STT_SECRET_4="${CLOVA_STT_SECRET_4:-}" \
    --from-literal=BACKEND_API_KEY="${BACKEND_API_KEY:-}" \
    --from-literal=TTS_SERVER_URL="${TTS_SERVER_URL:-}" \
    --from-literal=NCP_CLOVASTUDIO_API_KEY="${NCP_CLOVASTUDIO_API_KEY:-}" \
    --from-literal=CLOVA_ROUTER_ID="${CLOVA_ROUTER_ID:-}" \
    --from-literal=CLOVA_ROUTER_VERSION="${CLOVA_ROUTER_VERSION:-1}" \
    --from-literal=LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-}" \
    --from-literal=LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-}" \
    --from-literal=LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-https://cloud.langfuse.com}" \
    --from-literal=LANGFUSE_TRACING_ENABLED="${LANGFUSE_TRACING_ENABLED:-true}" \
    --from-literal=GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
    --from-literal=GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}" \
    --from-literal=GOOGLE_REDIRECT_URI="${GOOGLE_REDIRECT_URI:-}" \
    --from-literal=NAVER_CLIENT_ID="${NAVER_CLIENT_ID:-}" \
    --from-literal=NAVER_CLIENT_SECRET="${NAVER_CLIENT_SECRET:-}" \
    --from-literal=NAVER_REDIRECT_URI="${NAVER_REDIRECT_URI:-}" \
    --from-literal=CLOUDFLARE_TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "✅ Secret synced: ${NAMESPACE}/${SECRET_NAME}"
