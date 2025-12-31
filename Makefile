.PHONY: help install dev dev-fe dev-be build clean
.PHONY: docker-up docker-down docker-logs docker-build docker-rebuild
.PHONY: db-migrate db-upgrade db-downgrade
.PHONY: infra-up infra-down backend-up backend-down

# 기본 변수
DOCKER_COMPOSE = docker-compose -f docker/docker-compose.yml

# ===================
# Help
# ===================
help:
	@echo "Mit - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        - Install all dependencies"
	@echo "  make dev            - Run dev servers (FE + BE locally)"
	@echo "  make dev-fe         - Run frontend dev server"
	@echo "  make dev-be         - Run backend dev server"
	@echo ""
	@echo "Docker (All services):"
	@echo "  make docker-up      - Start all services (infra + backend)"
	@echo "  make docker-down    - Stop all services"
	@echo "  make docker-logs    - View all logs"
	@echo "  make docker-build   - Build backend image"
	@echo "  make docker-rebuild - Rebuild backend image (no cache)"
	@echo ""
	@echo "Docker (Selective):"
	@echo "  make infra-up       - Start infra only (DB, Redis, MinIO)"
	@echo "  make infra-down     - Stop infra only"
	@echo "  make backend-up     - Start backend container"
	@echo "  make backend-down   - Stop backend container"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate m=MSG - Create new migration"
	@echo "  make db-upgrade     - Apply migrations"
	@echo "  make db-downgrade   - Rollback last migration"
	@echo ""
	@echo "Build:"
	@echo "  make build          - Build frontend for production"
	@echo "  make clean          - Clean build artifacts"

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
# Docker - All Services
# ===================
docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f

docker-build:
	$(DOCKER_COMPOSE) build backend

docker-rebuild:
	$(DOCKER_COMPOSE) build --no-cache backend

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

backend-logs:
	$(DOCKER_COMPOSE) logs -f backend

# ===================
# Database Migrations
# ===================
db-migrate:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

db-upgrade:
	cd backend && uv run alembic upgrade head

db-downgrade:
	cd backend && uv run alembic downgrade -1

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
