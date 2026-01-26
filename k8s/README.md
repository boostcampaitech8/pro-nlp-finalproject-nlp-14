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
# 1. 클러스터 생성 (최초 1회)
make k8s-setup

# 2. 전체 빌드 및 배포
make k8s-deploy

# 3. 포트 포워딩
make k8s-pf

# 4. Postgress 마이그레이션
make k8s-migrate

# 5. Neo4j 스키마 업데이트 (제약조건 + 인덱스)
make k8s-neo4j-update

# 6. fe / be 로컬 실행
make dev

# localhost:3000 : 실시간 반영
# localhost : 하단 재빌드를 통해 반영
```

### 개별 서비스 재빌드

```bash
make k8s-push           # 전체 빌드 & 재시작
make k8s-push-be        # Backend 빌드 & 재시작
make k8s-push-fe        # Frontend 빌드 & 재시작
make k8s-push-worker    # Worker 빌드 & 재시작
```

### 상태 확인

```bash
make k8s-status              # Pod 상태
make k8s-logs svc=backend    # 로그 보기
kubectl -n mit logs job/realtime-worker-meeting-<meetingid>
make k8s-db-status           # 마이그레이션 상태
```

### 정리

```bash
make k8s-clean
```

## 프로덕션 환경 (k3s)

### 설정

```bash
# .env 파일 생성 및 시크릿 설정
cp .env.prod.example .env
# .env 파일에 실제 시크릿 값 입력

# 배포
make k8s-deploy-prod
```

## Makefile 타겟 요약

| 타겟 | 설명 |
|------|------|
| `k8s-setup` | k3d 클러스터 생성 |
| `k8s-deploy` | 로컬 배포 (빌드 + 배포) |
| `k8s-deploy-prod` | 프로덕션 배포 |
| `k8s-push` | 전체 빌드 & 재시작 |
| `k8s-push-be` | Backend 빌드 & 재시작 |
| `k8s-push-fe` | Frontend 빌드 & 재시작 |
| `k8s-push-worker` | Worker 빌드 & 재시작 |
| `k8s-migrate` | DB 마이그레이션 실행 |
| `k8s-db-status` | DB 마이그레이션 상태 확인 |
| `k8s-neo4j-update` | Neo4j 스키마 업데이트 (제약조건 + 인덱스) |
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
                                               +--> /storage/* --> minio:9000
                                               +--> /*         --> static files

backend:8000 --> postgres-postgresql:5432  (PostgreSQL)
               --> redis-master:6379        (Redis)
               --> minio:9000               (MinIO)
               --> lk-server:80             (LiveKit)
               --> neo4j:7687               (Neo4j Bolt)
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
│   ├── deploy.sh         # 배포
│   └── cleanup.sh        # 클러스터 삭제
├── helmfile.yaml.gotmpl  # Helmfile 메인 설정
└── k3d-config.yaml       # k3d 클러스터 설정
```

## 외부 차트

| 차트 | 용도 |
|------|------|
| bitnami/postgresql | PostgreSQL 15 |
| bitnami/redis | Redis 7 |
| minio/minio | 오브젝트 스토리지 |
| livekit/livekit-server | WebRTC SFU |
| neo4j/neo4j | Graph DB (Community Edition) |
