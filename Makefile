# Sibyl - Development Makefile
# Quick commands for local development and testing

.PHONY: help install test clean reset-db quick-run run-full run-limit install-deps

# Default target
help:
	@echo "Sibyl Development Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  install          Install dependencies and setup environment"
	@echo "  install-deps     Install Python dependencies only"
	@echo ""
	@echo "Database Management:"
	@echo "  reset-db         Reset local database (delete and recreate)"
	@echo "  init-db          Initialize database with required tables"
	@echo ""
	@echo "Agent Runs:"
	@echo "  quick-run        Quick agent run with minimal limits (1 feed, 3 items, 1 event)"
	@echo "  run-limit        Agent run with custom limits (edit Makefile to adjust)"
	@echo "  run-full         Full agent run without limits"
	@echo "  run-offline      Offline agent run using test fixtures (no network required)"
	@echo ""
	@echo "Testing & Development:"
	@echo "  test             Run tests"
	@echo "  clean            Clean up temporary files and caches"
	@echo "  lint             Run linting checks"
	@echo ""
	@echo "Monitoring:"
	@echo "  audit-llm        Generate LLM usage audit report"
	@echo "  visualize-llm    Create LLM performance visualizations"

# Setup & Installation
install: install-deps init-db
	@echo "✅ Sibyl setup complete!"

install-deps:
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt

# Database Management
reset-db:
	@echo "🗑️  Resetting local database..."
	@if [ -f local.db ]; then rm local.db; fi
	@echo "✅ Database deleted"
	@echo "🔧 Initializing new database..."
	python -m app.cli init-db
	@echo "✅ Database reset complete!"

init-db:
	@echo "🔧 Initializing database..."
	python -m app.cli init-db

# Agent Runs
quick-run:
	@echo "🚀 Running quick agent cycle (1 feed, 3 items per feed, 1 proto event)..."
	python -m app.cli run-cycle --all --max-feeds 1 --max-evidence-per-feed 3 --max-proto-events 1

run-limit:
	@echo "⚡ Running agent cycle with custom limits (2 feeds, 5 items per feed, 2 proto events)..."
	python -m app.cli run-cycle --all --max-feeds 2 --max-evidence-per-feed 5 --max-proto-events 2

run-full:
	@echo "🔥 Running full agent cycle without limits..."
	python -m app.cli run-cycle --all

run-offline:
	@echo "📱 Running agent cycle in offline mode with test fixtures..."
	python -m app.cli run-cycle --all --offline --max-feeds 1 --max-evidence-per-feed 3 --max-proto-events 1

# Testing & Development
test:
	@echo "🧪 Running tests..."
	python -m pytest tests/ -v

clean:
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete!"

lint:
	@echo "🔍 Running linting checks..."
	@echo "Note: Install flake8 or similar linter for full linting support"
	@python -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('app/**/*.py', recursive=True)]" && echo "✅ Basic syntax check passed"

# Monitoring & Analysis
audit-llm:
	@echo "📊 Generating LLM usage audit report..."
	python -m app.cli audit-llm --days 7

visualize-llm:
	@echo "📈 Creating LLM performance visualizations..."
	python -m app.cli visualize-llm --all --days 7

# Development workflow shortcuts
dev-reset: reset-db quick-run
	@echo "🔄 Development reset complete - fresh DB + quick run!"

dev-cycle: quick-run
	@echo "🔄 Quick development cycle complete!"

dev-offline: reset-db run-offline
	@echo "🔄 Offline development reset complete - fresh DB + offline run!"

dev-offline-cycle: run-offline
	@echo "🔄 Offline development cycle complete!"

# Docker commands (if needed)
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t sibyl -f docker/Dockerfile .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run --rm -it sibyl

# Environment setup
venv:
	@echo "🐍 Creating virtual environment..."
	python -m venv .venv
	@echo "✅ Virtual environment created. Activate with: source .venv/bin/activate"

# Quick development workflow
dev: install quick-run
	@echo "🎉 Development environment ready!"
