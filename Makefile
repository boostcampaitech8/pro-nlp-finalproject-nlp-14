.PHONY: help install dev dev-fe dev-be dev-worker dev-arq build clean test-fe graph
.PHONY: db-migrate db-upgrade db-downgrade neo4j-init neo4j-seed
.PHONY: k8s-setup k8s-infra k8s-deploy
.PHONY: k8s-push k8s-push-be k8s-push-fe k8s-build-worker k8s-push-worker
.PHONY: k8s-pf k8s-clean k8s-status k8s-logs

# 기본 변수
DEV_OAUTH_ENV = \
	NAVER_REDIRECT_URI=http://localhost:3000/auth/naver/callback \
	GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback

# ===================
# Help
# ===================
help:
	@echo "Mit - Development Commands"
	@echo ""
	@echo "Setup & Development:"
	@echo "  make install        - Install all dependencies"
	@echo "  make dev            - Run dev servers (FE + BE)"
	@echo "  make dev-fe         - Run frontend dev server (http://localhost:3000)"
	@echo "  make dev-be         - Run backend dev server (http://localhost:8000)"
	@echo "  make dev-worker     - Run realtime worker"
	@echo "  make dev-arq        - Run arq worker"
	@echo ""
	@echo "Graph:"
	@echo "  make graph          - Run LangGraph orchestrator (interactive)"
	@echo ""
	@echo "Test & Build:"
	@echo "  make test-fe        - Run frontend tests"
	@echo "  make build          - Build frontend for production"
	@echo "  make clean          - Clean build artifacts"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate m=MSG - Create new migration"
	@echo "  make db-upgrade       - Apply migrations"
	@echo "  make db-downgrade     - Rollback last migration"
	@echo "  make neo4j-init       - Initialize Neo4j schema"
	@echo "  make neo4j-seed ARGS  - Seed Neo4j with test data"
	@echo ""
	@echo "Kubernetes (k8s) - 로컬 개발:"
	@echo "  make k8s-setup        - k3d 클러스터 생성"
	@echo "  make k8s-infra        - 인프라 배포 (Redis, LiveKit)"
	@echo "  make k8s-deploy       - 전체 배포"
	@echo "  make k8s-push         - 전체 빌드 & 재시작"
	@echo "  make k8s-push-be      - Backend 빌드 & 재시작"
	@echo "  make k8s-push-fe      - Frontend 빌드 & 재시작"
	@echo "  make k8s-build-worker - Worker 이미지 빌드"
	@echo "  make k8s-push-worker  - Worker 빌드 & 재시작"
	@echo "  make k8s-pf           - 포트 포워딩"
	@echo "  make k8s-status       - Pod 상태 확인"
	@echo "  make k8s-logs svc=X   - 로그 보기 (backend|frontend|worker)"
	@echo "  make k8s-clean        - 클러스터 삭제"

# ===================
# Setup & Development
# ===================
install:
	pnpm install
	pnpm --filter @mit/shared-types build
	cd backend && uv sync
	cd backend/worker && uv sync
	cd backend/worker && mkdir -p ./build && uv run python -m grpc_tools.protoc -I=. --python_out=./build --grpc_python_out=./build nest.proto

dev:
	$(DEV_OAUTH_ENV) pnpm run dev

dev-fe:
	pnpm run dev:fe

dev-be:
	cd backend && $(DEV_OAUTH_ENV) uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	pnpm run dev:worker

dev-arq:
	cd backend && uv run python -m app.workers.run_worker

# ===================
# Graph
# ===================
graph:
	cd backend && PYTHONPATH=$(shell pwd)/backend:$$PYTHONPATH uv run python app/infrastructure/graph/main.py

# ===================
# Test & Build
# ===================
test-fe:
	pnpm --filter frontend test:run

build:
	pnpm --filter frontend build

clean:
	rm -rf frontend/dist
	rm -rf backend/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ===================
# Database
# ===================
db-migrate:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

db-upgrade:
	cd backend && uv run alembic upgrade head

db-downgrade:
	cd backend && uv run alembic downgrade -1

neo4j-seed:
	cd backend && uv run python seeds/neo4j_seed.py $(ARGS)

neo4j-init:
	cd backend && uv run python neo4j/init_schema.py

# ===================
# Kubernetes (k8s)
# ===================
K8S_REGISTRY = localhost:5111
K8S_DIR = k8s
K8S_SELECTOR = $(if $(svc),--selector svc=$(svc),)

k8s-setup:
	@./$(K8S_DIR)/scripts/setup-k3d.sh

k8s-infra:
	@echo "=== 1/2: Secret 생성 ==="
	@kubectl create namespace mit --dry-run=client -o yaml | kubectl apply -f -
	@./$(K8S_DIR)/scripts/deploy.sh local --selector svc=mit --args '--set global.enabled=false --set backend.enabled=false --set frontend.enabled=false --set worker.enabled=false' 2>/dev/null || true
	@echo ""
	@echo "=== 2/2: 인프라 배포 ==="
	@./$(K8S_DIR)/scripts/deploy.sh local --selector type=infra

k8s-deploy:
	@if [ -z "$(svc)" ] || [ "$(svc)" = "mit" ]; then \
		./$(K8S_DIR)/scripts/build.sh local; \
	fi
	@./$(K8S_DIR)/scripts/deploy.sh local $(K8S_SELECTOR)

k8s-push:
	@./$(K8S_DIR)/scripts/build.sh
	@kubectl -n mit rollout restart deployment/backend deployment/frontend deployment/worker

k8s-push-be:
	@docker build -t $(K8S_REGISTRY)/mit-backend:latest -f backend/Dockerfile backend
	@docker push $(K8S_REGISTRY)/mit-backend:latest
	@kubectl -n mit rollout restart deployment/backend

k8s-push-fe:
	@docker build -t $(K8S_REGISTRY)/mit-frontend:latest --build-arg VITE_API_URL=/api/v1 -f frontend/Dockerfile .
	@docker push $(K8S_REGISTRY)/mit-frontend:latest
	@kubectl -n mit rollout restart deployment/frontend

k8s-build-worker:
	@docker build -t $(K8S_REGISTRY)/mit-worker:latest -f backend/worker/Dockerfile backend/worker
	@docker push $(K8S_REGISTRY)/mit-worker:latest

k8s-push-worker: k8s-build-worker
	@kubectl -n mit rollout restart deployment/realtime-worker

k8s-pf:
	@echo "포트 포워딩 시작 (백그라운드)..."
	@nohup kubectl port-forward -n mit svc/redis-master 6379:6379 >/dev/null 2>&1 &
	@nohup kubectl port-forward -n mit svc/lk-server 7880:80 >/dev/null 2>&1 &
	@echo "  redis:    localhost:6379"
	@echo "  livekit:  localhost:7880"
	@echo ""
	@echo "  (PostgreSQL, Neo4j는 외부 서버 사용)"

k8s-clean:
	@k3d cluster delete mit

k8s-status:
	@kubectl -n mit get pods

k8s-logs:
	@kubectl -n mit logs -f deployment/$(svc)
