#!/bin/bash
# MIT 프로덕션 운영 유틸리티
# 배포(rollout)는 Argo CD ApplicationSet 자동 sync가 수행합니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$K8S_DIR")"

NAMESPACE="mit"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

bootstrap_argocd() {
    log_info "Argo CD root app bootstrap"
    "$SCRIPT_DIR/bootstrap-argocd.sh"
}

setup_ghcr_secret() {
    log_info "GHCR 인증 시크릿 설정"

    echo "GitHub Personal Access Token (read:packages 권한):"
    read -rs GITHUB_TOKEN
    echo ""

    echo "GitHub 사용자명:"
    read -r GITHUB_USERNAME

    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

    kubectl delete secret ghcr-secret -n "$NAMESPACE" 2>/dev/null || true
    kubectl create secret docker-registry ghcr-secret \
        --namespace="$NAMESPACE" \
        --docker-server=ghcr.io \
        --docker-username="$GITHUB_USERNAME" \
        --docker-password="$GITHUB_TOKEN"

    log_info "GHCR 시크릿 생성 완료"
}

status() {
    log_info "Argo CD 애플리케이션"
    kubectl get applications -n argocd || true
    echo ""
    log_info "Pod 상태"
    kubectl get pods -n "$NAMESPACE"
}

logs() {
    local svc="${1:-backend}"
    local meeting_id="${2:-}"

    if [ "$svc" = "worker" ]; then
        if [ -z "$meeting_id" ]; then
            log_error "worker 로그는 meetingId가 필요합니다"
            echo "사용법: $0 --logs worker <meetingId>"
            exit 1
        fi
        kubectl logs -n "$NAMESPACE" -f "job/realtime-worker-meeting-$meeting_id"
    else
        kubectl logs -n "$NAMESPACE" -f deployment/"$svc"
    fi
}

restart() {
    log_warn "GitOps 환경에서는 수동 재시작보다 Git 변경 + Argo sync를 권장합니다"
    kubectl rollout restart deployment backend frontend -n "$NAMESPACE"
    kubectl rollout status deployment backend frontend -n "$NAMESPACE"
}

migrate() {
    log_info "DB 마이그레이션 실행"
    kubectl exec -n "$NAMESPACE" deploy/backend -- /app/.venv/bin/alembic upgrade head
}

db_status() {
    log_info "DB 마이그레이션 상태"
    kubectl exec -n "$NAMESPACE" deploy/backend -- /app/.venv/bin/alembic current
}

neo4j_update() {
    log_info "Neo4j 스키마 업데이트"
    kubectl exec -n "$NAMESPACE" deploy/backend -- /app/.venv/bin/python /app/neo4j/init_schema.py
}

setup_network() {
    if [ -z "${LB_EXTERNAL_IP:-}" ]; then
        log_error "LB_EXTERNAL_IP 환경변수가 필요합니다"
        exit 1
    fi

    log_info "LiveKit 네트워크 설정: $LB_EXTERNAL_IP"

    sudo tee /etc/sysctl.d/99-livekit.conf >/dev/null <<EOC
# LiveKit WebRTC: loopback에 바인딩된 외부 IP로 들어오는 패킷 허용
net.ipv4.conf.all.rp_filter=2
net.ipv4.conf.default.rp_filter=2
net.ipv4.conf.ens4.rp_filter=2
EOC
    sudo sysctl --system >/dev/null

    sudo tee /etc/systemd/system/livekit-loopback-ip.service >/dev/null <<EOC
[Unit]
Description=Add LiveKit external IP to loopback
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/ip addr add ${LB_EXTERNAL_IP}/32 dev lo
ExecStop=/sbin/ip addr del ${LB_EXTERNAL_IP}/32 dev lo

[Install]
WantedBy=multi-user.target
EOC

    sudo systemctl daemon-reload
    sudo systemctl enable --now livekit-loopback-ip.service

    log_info "네트워크 설정 완료"
    ip addr show dev lo | grep "$LB_EXTERNAL_IP" && log_info "loopback IP 확인: $LB_EXTERNAL_IP"
}

usage() {
    cat <<EOU
사용법: $0 [옵션]

배포 방식:
  - 프로덕션 배포는 Argo CD가 수행합니다.
  - bootstrap: ./k8s/scripts/bootstrap-argocd.sh

옵션:
  --bootstrap-argocd       root app 적용
  --status                 Argo app/Pod 상태 확인
  --logs [svc]             로그 (backend|frontend)
  --logs worker <id>       worker 로그
  --restart                backend/frontend 재시작
  --migrate                DB 마이그레이션 실행
  --db-status              DB 마이그레이션 상태
  --neo4j-update           Neo4j 스키마 업데이트
  --setup-ghcr             GHCR 인증 시크릿 생성
  --setup-network          LiveKit 네트워크 설정 (sudo 필요)
  --help                   도움말
EOU
}

case "${1:-}" in
    --bootstrap-argocd)
        bootstrap_argocd
        ;;
    --status)
        status
        ;;
    --logs)
        logs "${2:-}" "${3:-}"
        ;;
    --restart)
        restart
        ;;
    --migrate)
        migrate
        ;;
    --db-status)
        db_status
        ;;
    --neo4j-update)
        neo4j_update
        ;;
    --setup-ghcr)
        setup_ghcr_secret
        ;;
    --setup-network)
        ENV_FILE="$ROOT_DIR/.env"
        if [ -f "$ENV_FILE" ]; then
            set -a
            source "$ENV_FILE"
            set +a
        fi
        setup_network
        ;;
    --help|-h)
        usage
        ;;
    "")
        log_warn "직접 배포는 비활성화되었습니다. Argo CD reconcile을 사용하세요."
        usage
        exit 1
        ;;
    *)
        log_error "알 수 없는 옵션: $1"
        usage
        exit 1
        ;;
esac
