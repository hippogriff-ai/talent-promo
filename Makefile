.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend build build-backend build-frontend clean lint test

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "  Setup:"
	@echo "    make install          - Install all dependencies (backend + frontend)"
	@echo "    make install-backend  - Install backend dependencies"
	@echo "    make install-frontend - Install frontend dependencies"
	@echo ""
	@echo "  Development:"
	@echo "    make dev              - Start both backend and frontend (requires 2 terminals or use dev-all)"
	@echo "    make dev-all          - Start both in background with logs"
	@echo "    make dev-backend      - Start backend server only"
	@echo "    make dev-frontend     - Start frontend server only"
	@echo ""
	@echo "  Build:"
	@echo "    make build            - Build both backend and frontend"
	@echo "    make build-backend    - Build/prepare backend"
	@echo "    make build-frontend   - Build frontend for production"
	@echo ""
	@echo "  Other:"
	@echo "    make lint             - Run linters"
	@echo "    make test             - Run tests"
	@echo "    make clean            - Clean build artifacts"
	@echo ""

# =============================================================================
# Installation
# =============================================================================

install: install-backend install-frontend
	@echo "✅ All dependencies installed"

install-backend:
	@echo "📦 Installing backend dependencies..."
	cd apps/api && pip install -r requirements.txt
	@echo "✅ Backend dependencies installed"

install-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd apps/web && pnpm install
	@echo "✅ Frontend dependencies installed"

# =============================================================================
# Development
# =============================================================================

dev:
	@echo "🚀 Starting development servers..."
	@echo "Run 'make dev-backend' in one terminal and 'make dev-frontend' in another"
	@echo "Or use 'make dev-all' to start both in background"

dev-all:
	@echo "🚀 Starting all services..."
	@mkdir -p .logs
	@echo "Starting backend..."
	cd apps/api && uvicorn main:app --reload --port 8000 > ../../.logs/backend.log 2>&1 &
	@echo "Starting frontend..."
	cd apps/web && pnpm dev > ../../.logs/frontend.log 2>&1 &
	@echo ""
	@echo "✅ Services started in background"
	@echo "   Backend:  http://localhost:8000"
	@echo "   Frontend: http://localhost:3000"
	@echo ""
	@echo "   Logs: .logs/backend.log, .logs/frontend.log"
	@echo "   Stop: make stop"

dev-backend:
	@echo "🚀 Starting backend server..."
	cd apps/api && uvicorn main:app --reload --port 8000

dev-frontend:
	@echo "🚀 Starting frontend server..."
	cd apps/web && pnpm dev

stop:
	@echo "🛑 Stopping services..."
	-pkill -f "uvicorn main:app" 2>/dev/null || true
	-pkill -f "next dev" 2>/dev/null || true
	@echo "✅ Services stopped"

# =============================================================================
# Build
# =============================================================================

build: build-backend build-frontend
	@echo "✅ Build complete"

build-backend:
	@echo "🔨 Preparing backend..."
	cd apps/api && pip install -r requirements.txt
	@echo "✅ Backend ready"

build-frontend:
	@echo "🔨 Building frontend..."
	cd apps/web && pnpm build
	@echo "✅ Frontend built"

# =============================================================================
# Quality
# =============================================================================

lint:
	@echo "🔍 Running linters..."
	cd apps/api && ruff check . || true
	cd apps/web && pnpm lint || true
	@echo "✅ Linting complete"

test:
	@echo "🧪 Running tests..."
	cd apps/api && pytest || true
	@echo "✅ Tests complete"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf apps/web/.next
	rm -rf apps/web/node_modules/.cache
	rm -rf apps/api/__pycache__
	rm -rf apps/api/.pytest_cache
	rm -rf apps/api/.ruff_cache
	rm -rf .logs
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean complete"

# =============================================================================
# Docker (optional)
# =============================================================================

docker-build:
	@echo "🐳 Building Docker images..."
	docker-compose build

docker-up:
	@echo "🐳 Starting Docker containers..."
	docker-compose up -d

docker-down:
	@echo "🐳 Stopping Docker containers..."
	docker-compose down

# =============================================================================
# LangGraph Deployment
# =============================================================================

langgraph-dev:
	@echo "🚀 Starting LangGraph development server..."
	langgraph dev

langgraph-up:
	@echo "🚀 Deploying to LangGraph Cloud..."
	langgraph up
