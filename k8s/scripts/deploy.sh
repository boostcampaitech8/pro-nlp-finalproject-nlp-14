#!/bin/bash
# helmfile 배포 (local은 Secret 동기화 포함)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

# 환경 선택 (기본: local), 나머지 인자는 helmfile에 전달
ENV="${1:-local}"
shift 1 2>/dev/null || true

echo "=== $ENV 환경 배포 ==="

cd "$K8S_DIR"

# 로컬 환경은 배포 전에 Secret을 클러스터와 동기화
if [ "$ENV" = "local" ]; then
    "$SCRIPT_DIR/sync-app-secret.sh" local
fi

# helmfile 실행
# 추가 인자 예: --selector svc=postgres
helmfile -f helmfile.yaml.gotmpl -e "$ENV" apply "$@"

echo ""
echo "=== 배포 완료 ==="
echo "상태 확인: kubectl get pods -n mit"
