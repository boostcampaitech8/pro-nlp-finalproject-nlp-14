#!/bin/bash
# 환경변수 로드 후 helmfile 배포
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$K8S_DIR")"

# 환경 선택 (기본: local)
ENV="${1:-local}"

echo "=== $ENV 환경 배포 ==="

# .env 파일 로드
ENV_FILE="$ROOT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo ">>> $ENV_FILE 로드"
    set -a
    source "$ENV_FILE"
    set +a
fi

cd "$K8S_DIR"

# helmfile 실행 (시크릿은 .gotmpl에서 환경변수 참조)
helmfile -f helmfile.yaml.gotmpl -e "$ENV" apply

echo ""
echo "=== 배포 완료 ==="
echo "상태 확인: kubectl get pods -n mit"
