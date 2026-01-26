.PHONY: help install dev dev-fe dev-be build clean test-fe graph
.PHONY: docker-up docker-down docker-logs docker-build docker-rebuild
.PHONY: db-migrate db-upgrade db-downgrade db-shell db-users db-tables db-query
.PHONY: infra-up infra-down livekit-up livekit-down backend-up backend-down backend-rebuild backend-logs
.PHONY: frontend-up frontend-down frontend-rebuild frontend-logs
.PHONY: worker-build worker-rebuild worker-list worker-clean
.PHONY: show-usage backup backup-restore backup-list
.PHONY: neo4j-init neo4j-seed
.PHONY: k8s-setup k8s-deploy k8s-deploy-prod k8s-infra
.PHONY: k8s-push k8s-push-be k8s-push-fe k8s-build-worker k8s-push-worker
.PHONY: k8s-migrate k8s-db-status k8s-pf k8s-clean k8s-status k8s-logs 


# 기본 변수
DOCKER_COMPOSE = docker compose -f docker/docker-compose.yml

# ===================
# Help
# ===================
help:
	@echo "Mit - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        - Install all dependencies"
	@echo "  make dev            - Run dev servers (FE + BE locally)"
	@echo "  make dev-fe         - Run frontend dev server (http://localhost:3000)"
	@echo "  make dev-be         - Run backend dev server (http://localhost:8000)"
	@echo ""
	@echo "Graph:"
	@echo "  make graph          - Run LangGraph orchestrator (interactive)"
	@echo ""
	@echo "Test:"
	@echo "  make test-fe        - Run frontend tests"
	@echo ""
	@echo "Docker (All services):"
	@echo "  make docker-up      - Start all services (infra + frontend + backend)"
	@echo "  make docker-down    - Stop all services"
	@echo "  make docker-logs    - View all logs"
	@echo "  make docker-build   - Build all images"
	@echo "  make docker-rebuild - Rebuild all images (no cache)"
	@echo ""
	@echo "Docker (Selective):"
	@echo "  make infra-up         - Start infra only (DB, Redis, MinIO, Neo4j)"
	@echo "  make infra-down       - Stop infra only"
	@echo "  make livekit-up       - Start LiveKit stack (DB, Redis, MinIO, LiveKit)"
	@echo "  make livekit-down     - Stop LiveKit stack"
	@echo "  make backend-up       - Start backend container"
	@echo "  make backend-down     - Stop backend container"
	@echo "  make backend-rebuild  - Rebuild and restart backend"
	@echo "  make backend-logs     - View backend logs"
	@echo "  make frontend-up      - Start frontend container"
	@echo "  make frontend-down    - Stop frontend container"
	@echo "  make frontend-rebuild - Rebuild and restart frontend"
	@echo "  make frontend-logs    - View frontend logs"
	@echo ""
	@echo "Docker (Worker):"
	@echo "  make worker-build     - Build realtime-worker image"
	@echo "  make worker-rebuild   - Rebuild worker (no cache)"
	@echo "  make worker-list      - List all worker containers"
	@echo "  make worker-clean     - Remove all worker containers"
	@echo ""
	@echo "Database (PostgreSQL):"
	@echo "  make db-migrate m=MSG - Create new migration"
	@echo "  make db-upgrade     - Apply migrations"
	@echo "  make db-downgrade   - Rollback last migration"
	@echo "  make db-shell       - Open psql shell"
	@echo "  make db-users       - Show all users"
	@echo "  make db-tables      - Show all tables"
	@echo "  make db-query q=SQL - Run custom SQL query"
	@echo "  make neo4j-seed ARGS='옵션' - Seed Neo4j with test data"
	@echo "    예: make neo4j-seed ARGS='--clean'  또는  ARGS='--records=1000 --csv'"
	@echo ""
	@echo "Database (Neo4j):"
	@echo "  make neo4j-init     - Initialize Neo4j schema (constraints + indexes)"
	@echo ""
	@echo "Build:"
	@echo "  make build          - Build frontend for production"
	@echo "  make clean          - Clean build artifacts"
	@echo ""
	@echo "Monitoring:"
	@echo "  make show-usage     - Show disk usage (MinIO, PostgreSQL)"
	@echo ""
	@echo "Backup:"
	@echo "  make backup              - Backup PostgreSQL, MinIO, Redis"
	@echo "  make backup-list         - List available backups"
	@echo "  make backup-restore name=YYYYMMDD_HHMMSS - Restore from backup"
	@echo ""
	@echo "Kubernetes (k8s):"
	@echo "  make k8s-setup        - k3d 클러스터 생성"
	@echo "  make k8s-deploy       - 로컬 배포"
	@echo "  make k8s-deploy-prod  - 프로덕션 배포"
	@echo "  make k8s-infra        - 인프라만 배포 (DB, Redis, MinIO, LiveKit)"
	@echo "  make k8s-push         - 전체 빌드 & 재시작"
	@echo "  make k8s-push-be      - Backend 빌드 & 재시작"
	@echo "  make k8s-push-fe      - Frontend 빌드 & 재시작"
	@echo "  make k8s-push-worker  - Worker 빌드 & 재시작"
	@echo "  make k8s-migrate      - DB 마이그레이션 실행"
	@echo "  make k8s-db-status    - DB 마이그레이션 상태 확인"
	@echo "  make k8s-pf           - 포트 포워딩 (백그라운드)"
	@echo "  make k8s-status       - Pod 상태 확인"
	@echo "  make k8s-logs svc=X   - 로그 보기 (svc=backend|frontend|worker)"
	@echo "  make k8s-clean        - 클러스터 삭제"

# ===================
# Setup & Development
# ===================
install:
	pnpm install
	pnpm --filter @mit/shared-types build
	cd backend && uv sync
	cd backend/worker && uv sync

dev:
	pnpm run dev

dev-fe:
	pnpm run dev:fe

dev-be:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	pnpm run dev:worker

# ===================
# Graph
# ===================
graph:
	cd backend && PYTHONPATH=$(shell pwd)/backend:$$PYTHONPATH uv run python app/infrastructure/graph/main.py

# ===================
# Test
# ===================
test-fe:
	pnpm --filter frontend test:run

# ===================
# Docker - All Services
# ===================
docker-up: worker-build
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f

docker-build:
	$(DOCKER_COMPOSE) build

docker-rebuild:
	$(DOCKER_COMPOSE) build --no-cache
	$(DOCKER_COMPOSE) up -d

# ===================
# Docker - Infra Only
# ===================
infra-up:
	$(DOCKER_COMPOSE) up -d postgres redis minio neo4j
	@echo "Neo4j 준비 대기 중..."
	@until docker exec mit-neo4j wget -q --spider http://localhost:7474 2>/dev/null; do sleep 2; done
	@$(MAKE) neo4j-init

infra-down:
	$(DOCKER_COMPOSE) stop postgres redis minio neo4j

livekit-up: worker-build
	$(DOCKER_COMPOSE) up -d postgres redis minio livekit 

livekit-down:
	$(DOCKER_COMPOSE) stop postgres redis minio livekit


# ===================
# Docker - Backend Only
# ===================
backend-up:
	$(DOCKER_COMPOSE) up -d backend

backend-down:
	$(DOCKER_COMPOSE) stop backend

backend-rebuild:
	$(DOCKER_COMPOSE) build --no-cache backend
	$(DOCKER_COMPOSE) up -d backend

backend-logs:
	$(DOCKER_COMPOSE) logs -f backend

# ===================
# Docker - Frontend Only
# ===================
frontend-up:
	$(DOCKER_COMPOSE) up -d frontend

frontend-down:
	$(DOCKER_COMPOSE) stop frontend

frontend-rebuild:
	$(DOCKER_COMPOSE) build --no-cache frontend
	$(DOCKER_COMPOSE) up -d frontend

frontend-logs:
	$(DOCKER_COMPOSE) logs -f frontend

# ===================
# Docker - Worker
# ===================
worker-build:
	$(DOCKER_COMPOSE) --profile worker build realtime-worker

worker-rebuild:
	$(DOCKER_COMPOSE) --profile worker build --no-cache realtime-worker

worker-list:
	@docker ps -a --filter "name=realtime-worker" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"

worker-clean:
	@docker ps -a --filter "name=realtime-worker" -q | xargs -r docker rm -f

# ===================
# Database Migrations
# ===================
db-migrate:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

db-upgrade:
	cd backend && uv run alembic upgrade head

db-downgrade:
	cd backend && uv run alembic downgrade -1

db-shell:
	docker exec -it mit-postgres psql -U mit -d mit

db-users:
	@docker exec mit-postgres psql -U mit -d mit -c "SELECT id, email, name, auth_provider, created_at FROM users;"

db-tables:
	@docker exec mit-postgres psql -U mit -d mit -c "\dt"

db-query:
	@docker exec mit-postgres psql -U mit -d mit -c "$(q)"

neo4j-seed:
	cd backend && uv run python seeds/neo4j_seed.py $(ARGS)

# ===================
# Neo4j
# ===================
neo4j-init:
	@echo "Neo4j 스키마 초기화 중..."
	@cd backend && uv run python neo4j/init_schema.py

# ===================
# Build & Clean
# ===================
build:
	pnpm --filter frontend build

clean:
	rm -rf frontend/dist
	rm -rf backend/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ===================
# Monitoring
# ===================
show-usage:
	@echo ""
	@echo "=========================================="
	@echo "        Docker Volume Usage"
	@echo "=========================================="
	@printf "%-35s %s\n" "VOLUME" "SIZE"
	@printf "%-35s %s\n" "-----------------------------------" "----------"
	@docker system df -v 2>/dev/null | grep "docker_minio_data" | awk '{printf "%-35s %s\n", $$1, $$3}'
	@docker system df -v 2>/dev/null | grep "docker_postgres_data" | awk '{printf "%-35s %s\n", $$1, $$3}'
	@docker system df -v 2>/dev/null | grep "docker_redis_data" | awk '{printf "%-35s %s\n", $$1, $$3}'
	@docker system df -v 2>/dev/null | grep "docker_neo4j_data" | awk '{printf "%-35s %s\n", $$1, $$3}'
	@echo ""
	@echo "=========================================="
	@echo "        MinIO Bucket Usage"
	@echo "=========================================="
	@docker exec mit-minio sh -c 'mc alias set local http://localhost:9000 admin adminadmin >/dev/null 2>&1 && mc du local/ --depth 2' 2>/dev/null || echo "MinIO not running"
	@echo ""
	@echo "=========================================="
	@echo "        PostgreSQL Table Sizes"
	@echo "=========================================="
	@docker exec mit-postgres psql -U mit -d mit -c "\
		SELECT tablename AS table, \
		       pg_size_pretty(pg_total_relation_size('public.' || tablename)) AS size \
		FROM pg_tables \
		WHERE schemaname = 'public' \
		ORDER BY pg_total_relation_size('public.' || tablename) DESC;" 2>/dev/null || echo "PostgreSQL not running"
	@echo ""

# ===================
# Backup & Restore
# ===================
BACKUP_DIR = backup
BACKUP_TIMESTAMP = $(shell date +%Y%m%d_%H%M%S)

backup:
	@echo ""
	@echo "=========================================="
	@echo "        Creating Backup"
	@echo "        $(BACKUP_TIMESTAMP)"
	@echo "=========================================="
	@mkdir -p $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/postgres
	@mkdir -p $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/minio
	@mkdir -p $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/redis
	@echo ""
	@echo "[1/3] Backing up PostgreSQL..."
	@docker exec mit-postgres pg_dump -U mit mit > $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/postgres/mit.sql 2>/dev/null && \
		echo "      -> $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/postgres/mit.sql" || \
		echo "      [SKIP] PostgreSQL not running"
	@echo ""
	@echo "[2/3] Backing up MinIO..."
	@docker cp mit-minio:/data $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/minio/ 2>/dev/null && \
		echo "      -> $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/minio/data/" || \
		echo "      [SKIP] MinIO not running"
	@echo ""
	@echo "[3/3] Backing up Redis..."
	@docker exec mit-redis redis-cli BGSAVE >/dev/null 2>&1 && sleep 1 && \
		docker cp mit-redis:/data/dump.rdb $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/redis/ 2>/dev/null && \
		echo "      -> $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/redis/dump.rdb" || \
		echo "      [SKIP] Redis not running"
	@echo ""
	@echo "=========================================="
	@echo "        Backup Complete!"
	@echo "        Location: $(BACKUP_DIR)/$(BACKUP_TIMESTAMP)/"
	@echo "=========================================="
	@du -sh $(BACKUP_DIR)/$(BACKUP_TIMESTAMP) 2>/dev/null || true
	@echo ""

backup-list:
	@echo ""
	@echo "=========================================="
	@echo "        Available Backups"
	@echo "=========================================="
	@if [ -d "$(BACKUP_DIR)" ]; then \
		ls -1d $(BACKUP_DIR)/*/ 2>/dev/null | while read dir; do \
			name=$$(basename "$$dir"); \
			size=$$(du -sh "$$dir" 2>/dev/null | cut -f1); \
			printf "  %s  (%s)\n" "$$name" "$$size"; \
		done || echo "  No backups found"; \
	else \
		echo "  No backups found"; \
	fi
	@echo ""

backup-restore:
	@echo ""
	@echo "=========================================="
	@echo "        Restore from Backup"
	@echo "=========================================="
	@if [ -z "$(name)" ]; then \
		echo "Usage: make backup-restore name=YYYYMMDD_HHMMSS"; \
		echo ""; \
		echo "Available backups:"; \
		ls -1d $(BACKUP_DIR)/*/ 2>/dev/null | xargs -I {} basename {} || echo "  No backups found"; \
		echo ""; \
		exit 1; \
	fi
	@if [ ! -d "$(BACKUP_DIR)/$(name)" ]; then \
		echo "Error: Backup '$(name)' not found"; \
		exit 1; \
	fi
	@echo "Restoring from: $(BACKUP_DIR)/$(name)"
	@echo ""
	@echo "[1/3] Restoring PostgreSQL..."
	@if [ -f "$(BACKUP_DIR)/$(name)/postgres/mit.sql" ]; then \
		docker exec -i mit-postgres psql -U mit mit < $(BACKUP_DIR)/$(name)/postgres/mit.sql 2>/dev/null && \
		echo "      -> PostgreSQL restored" || echo "      [FAIL] PostgreSQL restore failed"; \
	else \
		echo "      [SKIP] No PostgreSQL backup found"; \
	fi
	@echo ""
	@echo "[2/3] Restoring MinIO..."
	@if [ -d "$(BACKUP_DIR)/$(name)/minio/data" ]; then \
		docker cp $(BACKUP_DIR)/$(name)/minio/data/. mit-minio:/data/ 2>/dev/null && \
		echo "      -> MinIO restored" || echo "      [FAIL] MinIO restore failed"; \
	else \
		echo "      [SKIP] No MinIO backup found"; \
	fi
	@echo ""
	@echo "[3/3] Restoring Redis..."
	@if [ -f "$(BACKUP_DIR)/$(name)/redis/dump.rdb" ]; then \
		docker exec mit-redis redis-cli SHUTDOWN NOSAVE 2>/dev/null || true; \
		sleep 1; \
		docker cp $(BACKUP_DIR)/$(name)/redis/dump.rdb mit-redis:/data/ 2>/dev/null; \
		$(DOCKER_COMPOSE) restart redis 2>/dev/null && \
		echo "      -> Redis restored" || echo "      [FAIL] Redis restore failed"; \
	else \
		echo "      [SKIP] No Redis backup found"; \
	fi
	@echo ""
	@echo "=========================================="
	@echo "        Restore Complete!"
	@echo "=========================================="
	@echo ""

# ===================
# Kubernetes (k8s)
# ===================
K8S_REGISTRY = localhost:5111
K8S_DIR = k8s

k8s-setup:
	@./$(K8S_DIR)/scripts/setup-k3d.sh

k8s-deploy:
	@./$(K8S_DIR)/scripts/deploy.sh local

k8s-deploy-prod:
	@./$(K8S_DIR)/scripts/deploy.sh prod

k8s-infra: k8s-build-worker
	@./$(K8S_DIR)/scripts/deploy.sh local
	@kubectl -n mit scale deployment/backend --replicas=0
	@kubectl -n mit scale deployment/frontend --replicas=0
	@kubectl -n mit scale deployment/realtime-worker --replicas=1

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

k8s-migrate:
	@kubectl exec -n mit deploy/backend -- /app/.venv/bin/alembic upgrade head

k8s-db-status:
	@kubectl exec -n mit deploy/backend -- /app/.venv/bin/alembic current

k8s-pf:
	@echo "포트 포워딩 시작 (백그라운드)..."
	@nohup kubectl port-forward -n mit svc/postgres-postgresql 5432:5432 >/dev/null 2>&1 &
	@nohup kubectl port-forward -n mit svc/redis-master 6379:6379 >/dev/null 2>&1 &
	@nohup kubectl port-forward -n mit svc/minio 9000:9000 >/dev/null 2>&1 &
	@nohup kubectl port-forward -n mit svc/lk-server 7880:80 >/dev/null 2>&1 &
	@echo "  postgres: localhost:5432"
	@echo "  redis:    localhost:6379"
	@echo "  minio:    localhost:9000"
	@echo "  livekit:  localhost:7880"

k8s-clean:
	@./$(K8S_DIR)/scripts/cleanup.sh

k8s-status:
	@kubectl -n mit get pods

k8s-logs:
	@kubectl -n mit logs -f deployment/$(svc)
