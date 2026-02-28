#!/bin/bash
# local Helm 배포 유틸리티 (prod 배포는 Argo CD가 수행)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$K8S_DIR")"

ENV="${1:-local}"
shift 1 2>/dev/null || true

if [ "$ENV" != "local" ]; then
    echo "❌ prod 배포는 스크립트로 수행하지 않습니다. Argo CD reconcile을 사용하세요." >&2
    echo "   bootstrap: ./k8s/scripts/bootstrap-argocd.sh" >&2
    exit 1
fi

SELECTOR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --selector)
            SELECTOR="${2:-}"
            shift 2
            ;;
        *)
            echo "❌ 지원하지 않는 인자: $1" >&2
            exit 1
            ;;
    esac
done

NAMESPACE_DEFAULT="mit"
CATALOG_CORE_APPS="$K8S_DIR/argocd/catalogs/core-apps.yaml"
CATALOG_CORE_INFRA="$K8S_DIR/argocd/catalogs/core-infra.yaml"
CATALOG_OBSERVABILITY="$K8S_DIR/argocd/catalogs/prod-observability.yaml"
YAML_TOOL=""

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "❌ 필요한 명령어를 찾을 수 없습니다: $cmd" >&2
        exit 1
    fi
}

require_catalog() {
    local catalog="$1"
    if [ ! -f "$catalog" ]; then
        echo "❌ catalog 파일을 찾을 수 없습니다: $catalog" >&2
        exit 1
    fi
}

detect_yaml_tool() {
    if command -v yq >/dev/null 2>&1; then
        YAML_TOOL="yq"
        return
    fi

    if command -v python3 >/dev/null 2>&1; then
        YAML_TOOL="python"
        return
    fi

    echo "❌ YAML 파서를 찾을 수 없습니다. yq 또는 python3가 필요합니다." >&2
    exit 1
}

read_item_field() {
    local catalog="$1"
    local app_name="$2"
    local field="$3"
    local value

    if [ "$YAML_TOOL" = "yq" ]; then
        value="$(yq eval ".items[] | select(.appName == \"$app_name\") | .$field // \"\"" "$catalog")"
    else
        value="$(
            python3 - "$catalog" "$app_name" "$field" <<'PY'
import sys

catalog, app_name, field = sys.argv[1:4]

def strip_scalar(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    return raw

def read_block(lines, start_idx):
    block = []
    i = start_idx
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("    ") and not line.startswith("      "):
            break
        if line.startswith("      "):
            block.append(line[6:])
        elif line.strip() == "":
            block.append("")
        else:
            break
        i += 1
    return "\n".join(block).rstrip("\n"), i

def split_item_chunks(lines):
    chunks = []
    current = None
    for line in lines:
        if line.startswith("  - "):
            if current is not None:
                chunks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        chunks.append(current)
    return chunks

def parse_item(chunk):
    item = {}
    i = 0
    n = len(chunk)
    while i < n:
        line = chunk[i]
        if i == 0 and line.startswith("  - "):
            entry = line[4:]
        elif line.startswith("    ") and not line.startswith("      "):
            entry = line.strip()
        else:
            i += 1
            continue

        if ":" not in entry:
            i += 1
            continue

        key, raw = entry.split(":", 1)
        key = key.strip()
        raw = raw.strip()

        if raw in ("|", "|-"):
            block, next_i = read_block(chunk, i + 1)
            item[key] = block
            i = next_i
            continue

        item[key] = strip_scalar(raw)
        i += 1

    return item

def parse_catalog(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    chunks = split_item_chunks(lines)
    return [parse_item(chunk) for chunk in chunks]

items = parse_catalog(catalog)
item = next((x for x in items if x.get("appName") == app_name), None)
value = "" if item is None else item.get(field, "")
if value is None:
    value = ""
sys.stdout.write(str(value))
PY
        )"
    fi

    if [ "$value" = "null" ]; then
        value=""
    fi

    printf '%s' "$value"
}

assert_app_exists() {
    local catalog="$1"
    local app_name="$2"
    local found

    found="$(read_item_field "$catalog" "$app_name" "appName")"
    if [ -z "$found" ] || [ "$found" = "null" ]; then
        echo "❌ catalog($catalog)에서 appName=$app_name 항목을 찾을 수 없습니다." >&2
        exit 1
    fi
}

list_apps_by_wave() {
    local catalog="$1"

    if [ "$YAML_TOOL" = "yq" ]; then
        yq eval -r '.items | sort_by((.syncWave | tonumber)) | .[].appName' "$catalog"
        return
    fi

    python3 - "$catalog" <<'PY'
import sys

catalog = sys.argv[1]

def strip_scalar(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    return raw

def read_block(lines, start_idx):
    i = start_idx
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("    ") and not line.startswith("      "):
            break
        if line.startswith("      ") or line.strip() == "":
            i += 1
            continue
        break
    return i

def split_item_chunks(lines):
    chunks = []
    current = None
    for line in lines:
        if line.startswith("  - "):
            if current is not None:
                chunks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        chunks.append(current)
    return chunks

def parse_item(chunk):
    item = {}
    i = 0
    n = len(chunk)
    while i < n:
        line = chunk[i]
        if i == 0 and line.startswith("  - "):
            entry = line[4:]
        elif line.startswith("    ") and not line.startswith("      "):
            entry = line.strip()
        else:
            i += 1
            continue

        if ":" not in entry:
            i += 1
            continue

        key, raw = entry.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        if raw in ("|", "|-"):
            i = read_block(chunk, i + 1)
            continue

        item[key] = strip_scalar(raw)
        i += 1

    return item

def parse_catalog(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    chunks = split_item_chunks(lines)
    return [parse_item(chunk) for chunk in chunks]

items = parse_catalog(catalog)

def sync_wave(item):
    try:
        return int(str(item.get("syncWave", "0")))
    except Exception:
        return 0

for item in sorted(items, key=sync_wave):
    app_name = item.get("appName")
    if app_name:
        print(app_name)
PY
}

build_local_values_file() {
    local catalog="$1"
    local app_name="$2"
    local common
    local local_values
    local tmp

    common="$(read_item_field "$catalog" "$app_name" "valuesCommon")"
    local_values="$(read_item_field "$catalog" "$app_name" "valuesLocal")"

    tmp="$(mktemp)"

    if [ -n "$common" ]; then
        printf '%s\n' "$common" > "$tmp"
    fi

    if [ -n "$local_values" ]; then
        if [ -s "$tmp" ]; then
            printf '\n' >> "$tmp"
        fi
        printf '%s\n' "$local_values" >> "$tmp"
    fi

    printf '%s' "$tmp"
}

deploy_catalog_app() {
    local catalog="$1"
    local app_name="$2"
    local source_type
    local release_name
    local namespace
    local repo_url
    local chart
    local path
    local target_revision
    local values_file

    assert_app_exists "$catalog" "$app_name"

    source_type="$(read_item_field "$catalog" "$app_name" "sourceType")"
    release_name="$(read_item_field "$catalog" "$app_name" "releaseName")"
    namespace="$(read_item_field "$catalog" "$app_name" "namespace")"
    repo_url="$(read_item_field "$catalog" "$app_name" "repoURL")"
    chart="$(read_item_field "$catalog" "$app_name" "chart")"
    path="$(read_item_field "$catalog" "$app_name" "path")"
    target_revision="$(read_item_field "$catalog" "$app_name" "targetRevision")"

    if [ -z "$release_name" ]; then
        release_name="$app_name"
    fi

    if [ -z "$namespace" ]; then
        namespace="$NAMESPACE_DEFAULT"
    fi

    values_file="$(build_local_values_file "$catalog" "$app_name")"

    echo "=== local deploy: $release_name ($app_name) ==="

    case "$source_type" in
        helmRepo)
            if [ -z "$repo_url" ] || [ -z "$chart" ]; then
                echo "❌ $app_name: helmRepo 배포에 필요한 repoURL/chart가 없습니다." >&2
                rm -f "$values_file"
                exit 1
            fi

            if [ -n "$target_revision" ]; then
                helm upgrade --install "$release_name" "$chart" \
                    --repo "$repo_url" \
                    --namespace "$namespace" \
                    --create-namespace \
                    --version "$target_revision" \
                    -f "$values_file"
            else
                helm upgrade --install "$release_name" "$chart" \
                    --repo "$repo_url" \
                    --namespace "$namespace" \
                    --create-namespace \
                    -f "$values_file"
            fi
            ;;
        gitPath)
            if [ -z "$path" ]; then
                echo "❌ $app_name: gitPath 배포에 필요한 path가 없습니다." >&2
                rm -f "$values_file"
                exit 1
            fi

            helm upgrade --install "$release_name" "$ROOT_DIR/$path" \
                --namespace "$namespace" \
                --create-namespace \
                -f "$values_file"
            ;;
        *)
            echo "❌ 지원하지 않는 sourceType($app_name): $source_type" >&2
            rm -f "$values_file"
            exit 1
            ;;
    esac

    rm -f "$values_file"
}

deploy_stack() {
    local catalog="$1"
    local app_name

    while IFS= read -r app_name; do
        [ -z "$app_name" ] && continue
        deploy_catalog_app "$catalog" "$app_name"
    done < <(list_apps_by_wave "$catalog")
}

require_command helm
require_command kubectl
require_catalog "$CATALOG_CORE_APPS"
require_catalog "$CATALOG_CORE_INFRA"
require_catalog "$CATALOG_OBSERVABILITY"
detect_yaml_tool

echo "=== local Helm 배포 ==="
"$SCRIPT_DIR/sync-app-secret.sh" local

case "$SELECTOR" in
    "")
        deploy_stack "$CATALOG_CORE_INFRA"
        deploy_catalog_app "$CATALOG_CORE_APPS" "mit"
        deploy_stack "$CATALOG_OBSERVABILITY"
        ;;
    "type=infra")
        deploy_stack "$CATALOG_CORE_INFRA"
        ;;
    "type=observability")
        deploy_stack "$CATALOG_OBSERVABILITY"
        ;;
    "svc=mit"|"svc=backend"|"svc=frontend"|"svc=worker"|"svc=arq-worker")
        deploy_catalog_app "$CATALOG_CORE_APPS" "mit"
        ;;
    "svc=redis")
        deploy_catalog_app "$CATALOG_CORE_INFRA" "redis"
        ;;
    "svc=livekit")
        deploy_catalog_app "$CATALOG_CORE_INFRA" "livekit"
        ;;
    "svc=prometheus")
        deploy_catalog_app "$CATALOG_OBSERVABILITY" "prometheus"
        ;;
    "svc=loki")
        deploy_catalog_app "$CATALOG_OBSERVABILITY" "loki"
        ;;
    "svc=alloy")
        deploy_catalog_app "$CATALOG_OBSERVABILITY" "alloy"
        ;;
    "svc=grafana")
        deploy_catalog_app "$CATALOG_OBSERVABILITY" "grafana"
        ;;
    "svc=cloudflared")
        deploy_catalog_app "$CATALOG_OBSERVABILITY" "cloudflared"
        ;;
    *)
        echo "❌ 지원하지 않는 selector: $SELECTOR" >&2
        exit 1
        ;;
esac

echo ""
echo "✅ 배포 완료"
echo "상태 확인: kubectl get pods -n $NAMESPACE_DEFAULT"
