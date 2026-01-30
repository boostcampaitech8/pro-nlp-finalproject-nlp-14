#!/bin/bash
# MIT 프로덕션 K8s 배포 스크립트 (k3s 서버용)
#
# 사용법:
#   ./k8s/scripts/deploy-prod.sh                                    # 모든 서비스 latest 배포
#   ./k8s/scripts/deploy-prod.sh abc1234                            # 모든 서비스 동일 태그 배포
#   BACKEND_TAG=abc ./k8s/scripts/deploy-prod.sh                    # backend만 특정 태그
#   BACKEND_TAG=a FRONTEND_TAG=b ./k8s/scripts/deploy-prod.sh       # 서비스별 개별 태그
#   ./k8s/scripts/deploy-prod.sh --setup-ghcr                       # GHCR 인증 시크릿 설정 (최초 1회)
#   ./k8s/scripts/deploy-prod.sh --rollback                         # 이전 버전으로 롤백
#   ./k8s/scripts/deploy-prod.sh --status                           # 현재 배포 상태 확인
#   ./k8s/scripts/deploy-prod.sh --logs backend                     # backend 로그 확인
#   ./k8s/scripts/deploy-prod.sh --help                             # 도움말
#
# 사전 요구사항:
#   - kubectl이 k3s 클러스터에 연결된 상태
#   - helmfile 설치 (https://github.com/helmfile/helmfile)
#   - .env.prod 파일 (시크릿 환경변수)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$K8S_DIR")"

NAMESPACE="mit"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# GHCR 인증 시크릿 설정 (최초 1회)
setup_ghcr_secret() {
    log_info "GHCR 인증 시크릿 설정"

    echo "GitHub Personal Access Token (read:packages 권한):"
    read -s GITHUB_TOKEN
    echo ""

    echo "GitHub 사용자명:"
    read GITHUB_USERNAME

    # 네임스페이스 생성
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # 기존 시크릿 삭제 후 재생성
    kubectl delete secret ghcr-secret -n "$NAMESPACE" 2>/dev/null || true
    kubectl create secret docker-registry ghcr-secret \
        --namespace="$NAMESPACE" \
        --docker-server=ghcr.io \
        --docker-username="$GITHUB_USERNAME" \
        --docker-password="$GITHUB_TOKEN"

    log_info "GHCR 시크릿 생성 완료"
}

# 배포 실행
deploy() {
    local TAG="${1:-}"

    # 단일 태그 지정 시 모든 서비스에 적용
    if [ -n "$TAG" ]; then
        export BACKEND_TAG="${BACKEND_TAG:-$TAG}"
        export FRONTEND_TAG="${FRONTEND_TAG:-$TAG}"
        export WORKER_TAG="${WORKER_TAG:-$TAG}"
    fi

    log_info "배포 시작"
    log_info "  backend:  ${BACKEND_TAG:-latest}"
    log_info "  frontend: ${FRONTEND_TAG:-latest}"
    log_info "  worker:   ${WORKER_TAG:-latest}"

    # .env.prod 파일 로드
    ENV_FILE="$ROOT_DIR/.env"
    if [ -f "$ENV_FILE" ]; then
        log_info ".env 로드"
        set -a
        source "$ENV_FILE"
        set +a
    else
        log_error ".env 파일 없음: $ENV_FILE"
        exit 1
    fi

    cd "$K8S_DIR"

    # helmfile 배포
    helmfile -f helmfile.yaml.gotmpl -e prod apply

    log_info "배포 완료!"
    echo ""
    kubectl get pods -n "$NAMESPACE"
}

# 롤백
rollback() {
    log_info "이전 버전으로 롤백"
    helm rollback mit -n "$NAMESPACE"
    kubectl get pods -n "$NAMESPACE"
}

# 상태 확인
status() {
    log_info "Pod 상태:"
    kubectl get pods -n "$NAMESPACE"
    echo ""
    log_info "Helm 릴리즈:"
    helm list -n "$NAMESPACE"
    echo ""
    log_info "현재 이미지:"
    kubectl get deployment -n "$NAMESPACE" -o jsonpath='{range .items[*]}{.metadata.name}: {.spec.template.spec.containers[0].image}{"\n"}{end}'
}

# 로그 확인
logs() {
    local SVC="${1:-backend}"
    kubectl logs -n "$NAMESPACE" -f deployment/"$SVC"
}

# 메인
case "${1:-}" in
    --setup-ghcr)
        setup_ghcr_secret
        ;;
    --rollback)
        rollback
        ;;
    --status)
        status
        ;;
    --logs)
        logs "$2"
        ;;
    --help|-h)
        echo "사용법: $0 [옵션] [태그]"
        echo ""
        echo "옵션:"
        echo "  --setup-ghcr    GHCR 인증 시크릿 설정 (최초 1회)"
        echo "  --rollback      이전 버전으로 롤백"
        echo "  --status        현재 배포 상태 확인"
        echo "  --logs [svc]    로그 확인 (기본: backend)"
        echo "  --help, -h      도움말"
        echo ""
        echo "태그 지정:"
        echo "  $0                              # 모든 서비스 latest"
        echo "  $0 abc1234                      # 모든 서비스 동일 태그"
        echo "  BACKEND_TAG=abc $0              # backend만 특정 태그"
        echo "  BACKEND_TAG=a FRONTEND_TAG=b $0 # 서비스별 개별 태그"
        ;;
    *)
        deploy "$1"
        ;;
esac
