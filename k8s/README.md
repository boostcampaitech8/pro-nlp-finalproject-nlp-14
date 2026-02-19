# Kubernetes 가이드

k3d(로컬) / k3s(서버) 환경용 Helm 기반 배포 구성.

## 사전 요구사항

### macOS

```bash
brew install k3d helm helmfile kubectl

# helmfile 플러그인
helm plugin install https://github.com/databus23/helm-diff --verify=false
```

### Windows (WSL2 + Docker Desktop)

Docker Desktop 설정:
- Settings > Resources > WSL Integration > 사용할 distro 활성화
- Settings > Kubernetes > Enable Kubernetes **비활성화** (k3d와 충돌 방지)

WSL2 터미널에서:

```bash
# k3d
curl -fsSL https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# helmfile
curl -fsSL -o /tmp/helmfile.tar.gz \
  "https://github.com/helmfile/helmfile/releases/download/v1.2.3/helmfile_1.2.3_linux_amd64.tar.gz"
sudo tar -xzf /tmp/helmfile.tar.gz -C /usr/local/bin helmfile
rm -f /tmp/helmfile.tar.gz

# kubectl (WSL2 내 Linux 바이너리 별도 설치 권장)
curl -fsSLO "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm -f kubectl

# helm-diff (Helm 플러그인: helmfile diff 등에 사용)
helm plugin install https://github.com/databus23/helm-diff

```

## 로컬 개발 (k3d)

k8s 전체 배포 후, fe/be는 로컬에서도 실행하여 실시간 개발.

```bash
# postgresql, neo4j, livekit, redis, realtime worker (docker, k3s 도커 업로드)
make infra

# frontend, backend, arq worker 실행
make install
make dev
```

### 상태 확인

```bash
make k8s-status              # Pod 상태
make k8s-logs svc=backend    # 서비스 별 로그
make k8s-logs svc=frontend
kubectl -n mit logs job/realtime-worker-meeting-<meetingid> # 워커 로그
```

### 정리

```bash
make k8s-clean
```

## 프로덕션 배포 (k3s)

[deploy-prod.sh](scripts/deploy-prod.sh) 참고.

- Secret은 차트가 생성하지 않음
- prod Secret SSOT: `GCP Secret Manager -> ESO -> Secret/mit-secrets`
- local Secret 동기화: `k8s/scripts/sync-app-secret.sh` (local 전용)
- 비비밀 배포값 SSOT: `k8s/values/prod.yaml.gotmpl`
- 이미지 태그 SSOT: `k8s/image-tags.yaml`

## Makefile 타겟 요약

| 타겟 | 설명 |
|------|------|
| `k8s-setup` | k3d 클러스터 생성 |
| `k8s-infra` | 인프라 배포 (Redis, LiveKit) |
| `k8s-deploy` | 로컬 배포 (빌드 + 배포) |
| `k8s-push` | 전체 빌드 & 재시작 |
| `k8s-push-be` | Backend 빌드 & 재시작 |
| `k8s-push-fe` | Frontend 빌드 & 재시작 |
| `k8s-push-worker` | Worker 빌드 & 재시작 |
| `k8s-pf` | 포트 포워딩 (백그라운드) |
| `k8s-status` | Pod 상태 확인 |
| `k8s-logs svc=X` | 로그 보기 |
| `k8s-clean` | 클러스터 삭제 |

## 아키텍처

```
[Client] --> [Traefik Ingress :80/:443] --> [frontend nginx]
                                               |
                                               +--> /api/*     --> backend:8000
                                               +--> /livekit/* --> lk-server:80
                                               +--> /*         --> static files

backend:8000 --> PostgreSQL (외부)
               --> Neo4j (외부)
               --> redis-master:6379  (k8s)
               --> lk-server:80       (k8s)
```

## 디렉토리 구조

```
k8s/
├── charts/mit/           # 앱 Helm 차트
│   ├── templates/        # K8s 매니페스트 템플릿
│   └── values.yaml       # 기본값
├── values/
│   ├── local.yaml.gotmpl # 로컬 환경 설정
│   └── prod.yaml.gotmpl  # 프로덕션 환경 설정
├── scripts/
│   ├── setup-k3d.sh      # 클러스터 생성
│   ├── build.sh          # 이미지 빌드
│   ├── sync-app-secret.sh # 앱 Secret 동기화(local 전용)
│   ├── deploy.sh         # 배포
│   └── deploy-prod.sh    # 프로덕션 배포
├── helmfile.yaml.gotmpl  # Helmfile 메인 설정
├── image-tags.yaml       # 프로덕션 이미지 태그 SSOT
└── k3d-config.yaml       # k3d 클러스터 설정
```

## 외부 차트

| 차트 | 용도 |
|------|------|
| bitnami/redis | Redis 7 |
| livekit/livekit-server | WebRTC SFU |
