#!/bin/bash
# MIT 프로덕션 K8s 배포 스크립트 (k3s 서버용)
#
# 사용법:
#   ./k8s/scripts/deploy-prod.sh              # helmfile 배포 (설정 변경 시)
#   ./k8s/scripts/deploy-prod.sh --restart    # backend, frontend 재시작 (이미지 pull)
#   ./k8s/scripts/deploy-prod.sh --rollback   # 이전 버전으로 롤백
#   ./k8s/scripts/deploy-prod.sh --status     # 현재 배포 상태 확인
#   ./k8s/scripts/deploy-prod.sh --logs backend        # 로그 확인
#   ./k8s/scripts/deploy-prod.sh --logs worker <id>    # worker 로그 확인
#   ./k8s/scripts/deploy-prod.sh --migrate             # DB 마이그레이션 실행
#   ./k8s/scripts/deploy-prod.sh --db-status           # DB 마이그레이션 상태
#   ./k8s/scripts/deploy-prod.sh --neo4j-update        # Neo4j 스키마 업데이트
#   ./k8s/scripts/deploy-prod.sh --setup-ghcr          # GHCR 인증 시크릿 (최초 1회)
#   ./k8s/scripts/deploy-prod.sh --setup-network       # LiveKit 네트워크 설정 (노드 최초 1회)
#   ./k8s/scripts/deploy-prod.sh --help                # 도움말
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

# 이미지 태그 파일에서 환경변수 로드
load_image_tags() {
    local TAGS_FILE="$K8S_DIR/image-tags.yaml"
    if [ -f "$TAGS_FILE" ]; then
        log_info "이미지 태그 로드: $TAGS_FILE"

        # yq가 설치되어 있는지 확인
        if command -v yq &> /dev/null; then
            export BACKEND_TAG="${BACKEND_TAG:-$(yq '.backend' "$TAGS_FILE")}"
            export FRONTEND_TAG="${FRONTEND_TAG:-$(yq '.frontend' "$TAGS_FILE")}"
            export WORKER_TAG="${WORKER_TAG:-$(yq '.worker' "$TAGS_FILE")}"
        else
            # yq가 없으면 grep/sed로 파싱 (fallback)
            export BACKEND_TAG="${BACKEND_TAG:-$(grep '^backend:' "$TAGS_FILE" | sed 's/backend: *//')}"
            export FRONTEND_TAG="${FRONTEND_TAG:-$(grep '^frontend:' "$TAGS_FILE" | sed 's/frontend: *//')}"
            export WORKER_TAG="${WORKER_TAG:-$(grep '^worker:' "$TAGS_FILE" | sed 's/worker: *//')}"
        fi

        log_info "  Backend:  $BACKEND_TAG"
        log_info "  Frontend: $FRONTEND_TAG"
        log_info "  Worker:   $WORKER_TAG"
    else
        log_warn "이미지 태그 파일 없음, 기본값(latest) 사용"
    fi
}

# 배포 실행
deploy() {
    log_info "배포 시작"

    # .env 파일 로드
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

    # 이미지 태그 파일 로드 (환경변수로 덮어쓰기 가능)
    load_image_tags

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
    local MEETING_ID="$2"

    if [ "$SVC" = "worker" ]; then
        if [ -z "$MEETING_ID" ]; then
            log_error "worker 로그는 meetingId가 필요합니다"
            echo "사용법: $0 --logs worker <meetingId>"
            exit 1
        fi
        kubectl logs -n "$NAMESPACE" -f "job/realtime-worker-meeting-$MEETING_ID"
    else
        kubectl logs -n "$NAMESPACE" -f deployment/"$SVC"
    fi
}

# 재시작
restart() {
    log_info "backend, frontend 재시작"
    kubectl rollout restart deployment backend frontend -n "$NAMESPACE"
    kubectl rollout status deployment backend frontend -n "$NAMESPACE"
}

# DB 마이그레이션
migrate() {
    log_info "DB 마이그레이션 실행"
    kubectl exec -n "$NAMESPACE" deploy/backend -- /app/.venv/bin/alembic upgrade head
}

# DB 마이그레이션 상태
db_status() {
    log_info "DB 마이그레이션 상태"
    kubectl exec -n "$NAMESPACE" deploy/backend -- /app/.venv/bin/alembic current
}

# LiveKit 네트워크 설정 (노드 최초 1회, sudo 필요)
# - loopback에 외부 IP 바인딩 (GCP는 외부 IP가 NAT이라 LiveKit이 직접 감지 불가)
# - reverse path filtering 완화 (loopback에 바인딩된 외부 IP로 패킷 수신 허용)
setup_network() {
    if [ -z "$LB_EXTERNAL_IP" ]; then
        log_error "LB_EXTERNAL_IP 환경변수가 필요합니다"
        exit 1
    fi

    log_info "LiveKit 네트워크 설정: $LB_EXTERNAL_IP"

    # 1) sysctl - reverse path filtering 완화
    log_info "sysctl 설정 (rp_filter=2)"
    sudo tee /etc/sysctl.d/99-livekit.conf > /dev/null <<EOF
# LiveKit WebRTC: loopback에 바인딩된 외부 IP로 들어오는 패킷 허용
net.ipv4.conf.all.rp_filter=2
net.ipv4.conf.default.rp_filter=2
net.ipv4.conf.ens4.rp_filter=2
EOF
    sudo sysctl --system > /dev/null

    # 2) systemd - loopback에 외부 IP 영구 바인딩
    log_info "systemd 서비스 설정 (loopback IP)"
    sudo tee /etc/systemd/system/livekit-loopback-ip.service > /dev/null <<EOF
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
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable --now livekit-loopback-ip.service

    log_info "네트워크 설정 완료"
    log_info "  sysctl: /etc/sysctl.d/99-livekit.conf"
    log_info "  systemd: livekit-loopback-ip.service (enabled)"
    ip addr show dev lo | grep "$LB_EXTERNAL_IP" && log_info "  loopback IP 확인: $LB_EXTERNAL_IP ✓"
}

# Neo4j 스키마 업데이트
neo4j_update() {
    log_info "Neo4j 스키마 업데이트"
    kubectl exec -n "$NAMESPACE" deploy/backend -- /app/.venv/bin/python /app/neo4j/init_schema.py
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
        logs "$2" "$3"
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
    --setup-network)
        # .env에서 LB_EXTERNAL_IP 로드
        ENV_FILE="$ROOT_DIR/.env"
        if [ -f "$ENV_FILE" ]; then
            set -a; source "$ENV_FILE"; set +a
        fi
        setup_network
        ;;
    --help|-h)
        echo "사용법: $0 [옵션]"
        echo ""
        echo "배포:"
        echo "  (옵션 없음)               helmfile 배포 (설정 변경 시)"
        echo "  --restart                 backend, frontend 재시작 (이미지 pull)"
        echo "  --rollback                이전 버전으로 롤백"
        echo ""
        echo "상태 확인:"
        echo "  --status                  현재 배포 상태"
        echo "  --logs [svc]              로그 (backend|frontend)"
        echo "  --logs worker <id>        worker 로그"
        echo ""
        echo "DB/스키마:"
        echo "  --migrate                 DB 마이그레이션 실행"
        echo "  --db-status               DB 마이그레이션 상태"
        echo "  --neo4j-update            Neo4j 스키마 업데이트"
        echo ""
        echo "설정:"
        echo "  --setup-ghcr              GHCR 인증 시크릿 (최초 1회)"
        echo "  --setup-network           LiveKit 네트워크 설정 (노드 최초 1회, sudo 필요)"
        echo ""
        echo "이미지 태그:"
        echo "  기본값은 k8s/image-tags.yaml에서 로드"
        echo "  환경변수로 덮어쓰기 가능: BACKEND_TAG, FRONTEND_TAG, WORKER_TAG"
        ;;
    *)
        deploy
        ;;
esac
