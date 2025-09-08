# Sibyl - Intelligent Prediction System Makefile
# Core commands for the prediction pipeline: Mine → Judge → Predict → Visualize

.PHONY: help install test clean reset-db init-db

# Default target
help:
	@echo "🚀 Sibyl Prediction System Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  install          Install dependencies and setup environment"
	@echo "  install-deps     Install Python dependencies only"
	@echo "  venv             Create virtual environment"
	@echo ""
	@echo "Database Management:"
	@echo "  reset-db         Reset local database (delete and recreate)"
	@echo "  init-db          Initialize database with schema"
	@echo ""
	@echo "End-to-End Prediction Pipeline:"
	@echo "  run-e2e          Complete pipeline: mine → judge → predict → visualize"
	@echo "  run-e2e-quick    Quick pipeline with limited data"
	@echo "  run-e2e-kalshi   Pipeline with Kalshi markets only"
	@echo "  run-e2e-polymarket Pipeline with Polymarket markets only"
	@echo ""
	@echo "Individual Pipeline Steps:"
	@echo "  step-mine        Step 1: Mine prediction markets"
	@echo "  step-judge       Step 2: Judge event proposals"
	@echo "  step-predict     Step 3: Generate predictions"
	@echo "  step-visualize   Step 4: Start dashboard"
	@echo ""
	@echo "Dashboard & Visualization:"
	@echo "  serve-dashboard  Start local dashboard server"
	@echo "  view-dashboard   Open dashboard in browser"
	@echo ""
	@echo "Testing & Development:"
	@echo "  test             Run all tests"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  lint             Run linting checks"
	@echo ""
	@echo "Database Queries:"
	@echo "  query-db         Query complete database"
	@echo "  query-simple     Simple database overview"
	@echo "  query-proposals  Show event proposals"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Clean up temporary files and caches"

# Setup & Installation
install: install-deps init-db
	@echo "✅ Sibyl prediction system setup complete!"

install-deps:
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt

venv:
	@echo "🐍 Creating virtual environment..."
	python -m venv .venv
	@echo "✅ Virtual environment created. Activate with: source .venv/bin/activate"

# Database Management
reset-db:
	@echo "🗑️  Resetting local database..."
	@if [ -f local.db ]; then rm local.db; fi
	@echo "✅ Database files deleted"
	@echo "🔧 Initializing new database..."
	PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store(); store.create_all(); print('✅ Database initialized')"
	@echo "✅ Database reset complete!"

init-db:
	@echo "🔧 Initializing database..."
	PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store(); store.create_all(); print('✅ Database initialized')"

# End-to-End Prediction Pipeline
run-e2e: reset-db
	@echo "🚀 Running complete prediction pipeline..."
	@echo "Step 1: Mining prediction markets..."
	@$(MAKE) step-mine
	@echo "Step 2: Judging event proposals..."
	@$(MAKE) step-judge
	@echo "Step 3: Generating predictions..."
	@$(MAKE) step-predict
	@echo "Step 4: Starting visualization..."
	@$(MAKE) step-visualize
	@echo "✅ Complete pipeline finished!"

run-e2e-quick: reset-db
	@echo "🚀 Running quick prediction pipeline..."
	@echo "Step 1: Mining limited markets..."
	@$(MAKE) step-mine-quick
	@echo "Step 2: Judging proposals..."
	@$(MAKE) step-judge
	@echo "Step 3: Generating predictions..."
	@$(MAKE) step-predict
	@echo "Step 4: Starting visualization..."
	@$(MAKE) step-visualize
	@echo "✅ Quick pipeline finished!"

run-e2e-kalshi: reset-db
	@echo "🚀 Running Kalshi-only pipeline..."
	@echo "Step 1: Mining Kalshi markets..."
	@$(MAKE) step-mine-kalshi
	@echo "Step 2: Judging proposals..."
	@$(MAKE) step-judge
	@echo "Step 3: Generating predictions..."
	@$(MAKE) step-predict
	@echo "Step 4: Starting visualization..."
	@$(MAKE) step-visualize
	@echo "✅ Kalshi pipeline finished!"

run-e2e-polymarket: reset-db
	@echo "🚀 Running Polymarket-only pipeline..."
	@echo "Step 1: Mining Polymarket markets..."
	@$(MAKE) step-mine-polymarket
	@echo "Step 2: Judging proposals..."
	@$(MAKE) step-judge
	@echo "Step 3: Generating predictions..."
	@$(MAKE) step-predict
	@echo "Step 4: Starting visualization..."
	@$(MAKE) step-visualize
	@echo "✅ Polymarket pipeline finished!"

# Individual Pipeline Steps
step-mine:
	@echo "⛏️  Mining prediction markets from Kalshi and Polymarket..."
	PYTHONPATH=$$(pwd) python3 -m app.workflows.market_mining --platforms kalshi,polymarket --limit 50

step-mine-quick:
	@echo "⛏️  Mining limited markets for quick test..."
	PYTHONPATH=$$(pwd) python3 -m app.workflows.market_mining --platforms kalshi,polymarket --limit 10

step-mine-kalshi:
	@echo "⛏️  Mining Kalshi markets only..."
	PYTHONPATH=$$(pwd) python3 -m app.workflows.market_mining --platforms kalshi --limit 50

step-mine-polymarket:
	@echo "⛏️  Mining Polymarket markets only..."
	PYTHONPATH=$$(pwd) python3 -m app.workflows.market_mining --platforms polymarket --limit 50

step-judge:
	@echo "⚖️  Judging event proposals..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/judge_event_proposals.py --status-filter pending

step-predict:
	@echo "🔮 Generating predictions with research agent..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/test_enhanced_prediction.py

step-visualize:
	@echo "📊 Starting visualization dashboard..."
	@$(MAKE) serve-dashboard

# Dashboard & Visualization
serve-dashboard:
	@echo "🚀 Starting local server for prediction dashboard..."
	@echo "📊 Make sure to run 'make step-predict' first to generate data"
	cd docs && python3 serve.py

view-dashboard:
	@echo "🌐 Opening dashboard in browser..."
	@echo "Dashboard URL: http://localhost:8080"
	@echo "Make sure to run 'make serve-dashboard' first"

# Testing & Development
test:
	@echo "🧪 Running tests..."
	pytest tests/ -v

test-coverage:
	@echo "🧪 Running tests with coverage..."
	pytest tests/ --cov=app --cov-report=html --cov-report=term

lint:
	@echo "🔍 Running linting checks..."
	flake8 app/ tests/ --max-line-length=100

# Database Queries
query-db:
	@echo "📊 Querying complete database..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/query_database.py

query-simple:
	@echo "📊 Simple database overview..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/query_everything.py

query-proposals:
	@echo "📊 Showing event proposals..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/query_proposals.py

# Cleanup
clean:
	@echo "🧹 Cleaning up temporary files..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name ".pytest_cache" -delete
	@find . -type f -name ".coverage" -delete
	@rm -rf htmlcov/
	@echo "✅ Cleanup complete!"