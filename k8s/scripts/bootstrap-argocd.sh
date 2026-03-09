#!/bin/bash
# Argo CD root app bootstrap 스크립트
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl apply -f "$K8S_DIR/argocd/bootstrap/root-app.yaml"

echo "✅ Argo CD root app applied: argocd/mit-root"
