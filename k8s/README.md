# Kubernetes 가이드

Argo CD ApplicationSet 기반 GitOps 구성입니다.

## 배포 원칙

- `prod` 배포 실행 주체: Argo CD reconcile
- `local` 개발 실행 주체: `make infra`, `make dev`
- Secret SSOT
  - `prod`: GCP Secret Manager -> ESO -> `Secret/mit-secrets`
  - `local`: `k8s/scripts/sync-app-secret.sh`
- values SSOT
  - `k8s/argocd/catalogs/core-apps.yaml` (`mit`의 `valuesCommon/valuesProd/valuesLocal`)
  - `k8s/argocd/catalogs/core-infra.yaml` (infra external chart values)
  - `k8s/argocd/catalogs/prod-observability.yaml` (observability external chart values)
  - `k8s/image-tags.yaml` (`mit` 이미지 태그 SSOT)
- CI/CD
  - `ci.yml`: 이미지 빌드 + `k8s/image-tags.yaml` 갱신
  - 배포: Git 변경 후 Argo CD auto sync

## Argo CD 구성

### AppProject

- `k8s/argocd/appprojects/apps.yaml`

### ApplicationSet 3분할

- `k8s/argocd/applicationsets/core-infra.yaml`
  - redis, livekit
- `k8s/argocd/applicationsets/core-apps.yaml`
  - mit 차트 (backend/frontend/arq)
- `k8s/argocd/applicationsets/prod-observability.yaml`
  - prometheus, loki, alloy, grafana, cloudflared
- 카탈로그(앱 목록/메타): `k8s/argocd/catalogs/*.yaml`

### Sync 순서

- core-infra -> core-apps -> prod-observability
- sync-wave annotation으로 순서 보장

### Bootstrap

```bash
# Argo CD namespace/root app 적용
./k8s/scripts/bootstrap-argocd.sh
```

또는

```bash
./k8s/scripts/deploy-prod.sh --bootstrap-argocd
```

## 로컬 개발 (k3d)

```bash
# 1) 인프라 준비 (DB + k3d + redis/livekit + worker image)
make infra

# 2) 앱 개발 서버
make dev
```

선택 배포:

```bash
make k8s-infra     # redis/livekit
make k8s-observe   # prometheus/loki/alloy/grafana
make k8s-deploy    # local chart + infra/observability
```

## 차트 역할

### `charts/mit`

앱 전용 차트입니다.

- backend/frontend/arq
- 앱 공통 ConfigMap/secretRef 소비
- cloudflared/alloy-configmap 템플릿 없음

### `charts/cloudflared`

독립 차트입니다.

- `TUNNEL_TOKEN`은 values가 아니라 Secret 참조
- 기본 참조
  - `secretName: mit-secrets`
  - `secretKey: CLOUDFLARE_TUNNEL_TOKEN`
- prod-observability ApplicationSet에서만 배포

### Alloy 구성

- 별도 커스텀 chart 없이 `grafana/alloy` 공식 chart 사용
- `alloy.configMap.create=true`
- 설정 본문은 ApplicationSet `helm.values` inline에서 선언

## 스크립트 정책

- `k8s/scripts/deploy.sh`: local Helm 유틸리티
  - catalog에서 `valuesCommon + valuesLocal`을 읽어 로컬 Helm 배포
- `k8s/scripts/deploy-prod.sh`: 프로덕션 운영 유틸리티(배포 자체는 비활성화)
- `k8s/scripts/sync-app-secret.sh`: local 전용

## 디렉토리 구조

```text
k8s/
├── charts/
│   ├── mit/
│   └── cloudflared/
├── image-tags.yaml
├── argocd/
│   ├── appprojects/
│   │   └── apps.yaml
│   ├── applicationsets/
│   │   ├── core-apps.yaml
│   │   ├── core-infra.yaml
│   │   └── prod-observability.yaml
│   ├── catalogs/
│   │   ├── core-apps.yaml
│   │   ├── core-infra.yaml
│   │   └── prod-observability.yaml
│   └── bootstrap/
│       └── root-app.yaml
└── scripts/
    ├── bootstrap-argocd.sh
    ├── deploy.sh
    ├── deploy-prod.sh
    └── sync-app-secret.sh
```

## Deprecated

- Helmfile 기반 배포 (`helmfile.yaml.gotmpl`)는 제거되었습니다.
