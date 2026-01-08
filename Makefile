.PHONY: help install dev dev-fe dev-be build clean test-fe
.PHONY: docker-up docker-down docker-logs docker-build docker-rebuild
.PHONY: db-migrate db-upgrade db-downgrade db-shell db-users db-tables db-query
.PHONY: infra-up infra-down backend-up backend-down backend-rebuild backend-logs
.PHONY: frontend-up frontend-down frontend-rebuild frontend-logs
.PHONY: show-usage

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
	@echo "  make infra-up         - Start infra only (DB, Redis, MinIO)"
	@echo "  make infra-down       - Stop infra only"
	@echo "  make backend-up       - Start backend container"
	@echo "  make backend-down     - Stop backend container"
	@echo "  make backend-rebuild  - Rebuild and restart backend"
	@echo "  make backend-logs     - View backend logs"
	@echo "  make frontend-up      - Start frontend container"
	@echo "  make frontend-down    - Stop frontend container"
	@echo "  make frontend-rebuild - Rebuild and restart frontend"
	@echo "  make frontend-logs    - View frontend logs"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate m=MSG - Create new migration"
	@echo "  make db-upgrade     - Apply migrations"
	@echo "  make db-downgrade   - Rollback last migration"
	@echo "  make db-shell       - Open psql shell"
	@echo "  make db-users       - Show all users"
	@echo "  make db-tables      - Show all tables"
	@echo "  make db-query q=SQL - Run custom SQL query"
	@echo ""
	@echo "Build:"
	@echo "  make build          - Build frontend for production"
	@echo "  make clean          - Clean build artifacts"
	@echo ""
	@echo "Monitoring:"
	@echo "  make show-usage     - Show disk usage (MinIO, PostgreSQL)"

# ===================
# Setup & Development
# ===================
install:
	pnpm install
	pnpm --filter @mit/shared-types build
	cd backend && uv sync

dev:
	pnpm run dev

dev-fe:
	pnpm run dev:fe

dev-be:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ===================
# Test
# ===================
test-fe:
	pnpm --filter frontend test:run

# ===================
# Docker - All Services
# ===================
docker-up:
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
	$(DOCKER_COMPOSE) up -d postgres redis minio

infra-down:
	$(DOCKER_COMPOSE) stop postgres redis minio

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
