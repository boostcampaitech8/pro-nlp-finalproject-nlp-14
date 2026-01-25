#!/bin/bash
# k3d 클러스터 생성 (로컬 전용)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== k3d 클러스터 설정 ==="

if k3d cluster list 2>/dev/null | grep -q "^mit "; then
    echo "클러스터 'mit' 이미 존재"
    kubectl config use-context k3d-mit
else
    echo ">>> 클러스터 생성 중..."
    k3d cluster create --config "$K8S_DIR/k3d-config.yaml"
fi

kubectl cluster-info
echo ""
echo "=== 완료 ==="
echo ""
echo "다음 단계:"
echo "  1. 이미지 빌드: ./k8s/scripts/build.sh"
echo "  2. 배포: cd k8s && helmfile -e local apply"
