#!/bin/bash
# 정리 스크립트
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

case "${1:-}" in
    --all)
        echo ">>> Helmfile로 전체 삭제..."
        cd "$K8S_DIR"
        helmfile -e local destroy || true
        kubectl delete namespace mit --ignore-not-found
        ;;
    --cluster)
        echo ">>> k3d 클러스터 삭제..."
        k3d cluster delete mit
        ;;
    *)
        echo "사용법: $0 [--all|--cluster]"
        echo ""
        echo "  --all      전체 삭제 (helmfile destroy + namespace)"
        echo "  --cluster  k3d 클러스터 삭제"
        ;;
esac
