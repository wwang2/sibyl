
# Sibyl - Event Sourcing Prediction System Makefile
# Quick commands for local development and testing

.PHONY: help install test clean reset-db quick-run run-full run-offline install-deps test-workflow

# Default target
help:
	@echo "🚀 Sibyl Event Sourcing System Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  install          Install dependencies and setup environment"
	@echo "  install-deps     Install Python dependencies only"
	@echo "  venv             Create virtual environment"
	@echo ""
	@echo "Database Management:"
	@echo "  reset-db         Reset local database (delete and recreate)"
	@echo "  init-db          Initialize database with event sourcing tables"
	@echo "  migrate          Run database migrations"
	@echo ""
	@echo "Agentic Workflows:"
	@echo "  quick-run        Quick agentic workflow (1 feed, 3 items, 2 events)"
	@echo "  quick-offline    Quick offline workflow with test fixtures (no network)"
	@echo "  run-full         Full agentic workflow without limits"
	@echo "  run-offline      Offline workflow using test fixtures (no network)"
	@echo "  test-workflow    Test the complete event sourcing workflow"
	@echo ""
	@echo "Testing & Development:"
	@echo "  test             Run all tests"
	@echo "  test-agents      Test discovery and assessor agents"
	@echo "  visualize        Open event visualization in browser"
	@echo "  test-models      Test event sourcing models"
	@echo ""
	@echo "Database Query Tools:"
	@echo "  query-db         Query complete database (all tables)"
	@echo "  query-events     Query events and raw items only"
	@echo "  query-simple     Simple database query with counts and recent items"
	@echo "  query-all        Show everything in database with detailed breakdown"
	@echo "  query-everything Show COMPLETE database with all details and samples"
	@echo "  query-politics   Show all politics-related markets"
	@echo "  query-crypto     Show all crypto-related markets"
	@echo "  query-by-source  Show breakdown by data source (Kalshi/Polymarket)"
	@echo "  query-recent     Show all items from last 24 hours"
	@echo ""
	@echo "Prediction Market Mining:"
	@echo "  mine-markets     Mine both Kalshi and Polymarket (100 markets each)"
	@echo "  mine-kalshi      Mine Kalshi prediction markets only"
	@echo "  mine-polymarket  Mine Polymarket prediction markets only"
	@echo "  mine-politics    Mine politics-focused markets (Polymarket)"
	@echo "  mine-finance     Mine finance/markets-focused markets (Polymarket)"
	@echo "  mine-crypto      Mine crypto-focused markets (both platforms)"
	@echo ""
	@echo "Routine Workflows:"
	@echo "  workflow-scheduler    Start the complete workflow scheduler"
	@echo "  workflow-mining       Run market mining workflow once"
	@echo "  workflow-discovery    Run discovery workflow once"
	@echo "  workflow-prediction   Run prediction workflow once"
	@echo "  workflow-research     Run research workflow once"
	@echo "  clean            Clean up temporary files and caches"
	@echo "  lint             Run linting checks"
	@echo ""
	@echo "Monitoring & Analysis:"
	@echo "  audit-workflows  Generate workflow audit report"
	@echo "  audit-predictions Generate prediction performance report"
	@echo "  visualize-data   Create data flow visualizations"
	@echo ""
	@echo "Development Workflows:"
	@echo "  dev-reset        Reset DB + quick run (fresh start)"
	@echo "  dev-cycle        Quick development cycle"
	@echo "  dev-offline      Offline development (no network needed)"

# Setup & Installation
install: install-deps init-db
	@echo "✅ Sibyl event sourcing system setup complete!"

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
	@if [ -f test_agentic.db ]; then rm test_agentic.db; fi
	@if [ -f test_v2.db ]; then rm test_v2.db; fi
	@echo "✅ Database files deleted"
	@echo "🔧 Initializing new database with event sourcing schema..."
	PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store(); store.create_all(); print('✅ Database initialized')"
	@echo "✅ Database reset complete!"

init-db:
	@echo "🔧 Initializing database with event sourcing schema..."
	PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store(); store.create_all(); print('✅ Database initialized')"

migrate:
	@echo "🔄 Running database migrations..."
	alembic upgrade head

# Agentic Workflows
quick-run: init-db
	@echo "🚀 Running quick agentic workflow (1 feed, 3 items, 2 events)..."
	@PYTHONPATH=$$(pwd) python3 -m app.run_cycle --max-feeds 2 --max-items-per-feed 5 --max-events 5

run-full: init-db
	@echo "🔥 Running full agentic workflow without limits..."
	@PYTHONPATH=$$(pwd) python3 -m app.run_cycle

run-offline: init-db
	@echo "📱 Running agentic workflow in offline mode with test fixtures..."
	@PYTHONPATH=$$(pwd) python3 -m app.run_cycle --max-feeds 1 --max-items-per-feed 3 --max-events 2 --offline-mode

quick-offline: init-db
	@echo "🚀 Running quick offline workflow (1 feed, 3 items, 2 events) with test fixtures..."
	@PYTHONPATH=$$(pwd) python3 -m app.run_cycle --max-feeds 1 --max-items-per-feed 3 --max-events 2 --offline-mode

test-workflow:
	@echo "🧪 Testing complete event sourcing workflow..."
	@rm -f test_agentic.db
	@PYTHONPATH=$$(pwd) python3 temp_scripts/test_agentic_workflow.py

# Testing & Development
test:
	@echo "🧪 Running all tests..."
	PYTHONPATH=$$(pwd) python3 -m pytest tests/ -v

test-agents:
	@echo "🤖 Testing discovery and assessor agents..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/test_agentic_workflow.py

test-models:
	@echo "📊 Testing event sourcing models..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/test_event_sourcing_v2.py

# Database Query Tools
query-db:
	@echo "🔍 Querying complete database..."
	@PYTHONPATH=$$(pwd) python3 temp_scripts/query_database.py

query-events:
	@echo "🎲 Querying events and raw items..."
	@PYTHONPATH=$$(pwd) python3 temp_scripts/query_events_and_raw_items.py

clean:
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.db" -delete
	find . -type f -name "*.log" -delete
	@echo "✅ Cleanup complete!"

lint:
	@echo "🔍 Running linting checks..."
	@python -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('app/**/*.py', recursive=True)]" && echo "✅ Basic syntax check passed"

# Monitoring & Analysis
audit-workflows:
	@echo "📊 Generating workflow audit report..."
	@PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store('sqlite:///./local.db'); from app.core.models import WorkflowRun, ToolCall, AgentRun; session = store.get_session(); workflows = session.query(WorkflowRun).count(); tool_calls = session.query(ToolCall).count(); agent_runs = session.query(AgentRun).count(); print(f'📈 Workflow Audit Report:'); print(f'  - Workflow Runs: {workflows}'); print(f'  - Tool Calls: {tool_calls}'); print(f'  - Agent Runs: {agent_runs}'); session.close()"

audit-predictions:
	@echo "📊 Generating prediction performance report..."
	@PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store('sqlite:///./local.db'); from app.core.models import Prediction, PredictionScore; session = store.get_session(); predictions = session.query(Prediction).count(); scores = session.query(PredictionScore).count(); print(f'📈 Prediction Performance Report:'); print(f'  - Total Predictions: {predictions}'); print(f'  - Performance Scores: {scores}'); session.close()"

visualize-data:
	@echo "📈 Creating data flow visualizations..."
	@echo "📊 Event Sourcing Flow:"
	@echo "  RawItems → EventProposals → Events → Predictions"
	@echo "📊 Workflow Transparency:"
	@echo "  WorkflowRuns → ToolCalls → LLM Interactions"
	@echo "📊 Attribution Chain:"
	@echo "  Predictions → PredictionAttributions → RawItems"

# Development workflow shortcuts
dev-reset: reset-db quick-run
	@echo "🔄 Development reset complete - fresh DB + quick run!"

dev-cycle: quick-run
	@echo "🔄 Quick development cycle complete!"

dev-offline: reset-db run-offline
	@echo "🔄 Offline development reset complete - fresh DB + offline run!"

dev-offline-cycle: run-offline
	@echo "🔄 Offline development cycle complete!"

# Event Sourcing specific commands
events-status:
	@echo "📊 Event Status Report:"
	@PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store('sqlite:///./local.db'); from app.core.models import Event; session = store.get_session(); [print(f'  - {state.capitalize()}: {session.query(Event).filter(Event.state == state).count()}') for state in ['draft', 'active', 'locked', 'resolved', 'canceled', 'archived']]; session.close()"

proposals-status:
	@echo "📊 Event Proposal Status Report:"
	@PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store('sqlite:///./local.db'); from app.core.models import EventProposal; session = store.get_session(); [print(f'  - {status.capitalize()}: {session.query(EventProposal).filter(EventProposal.status == status).count()}') for status in ['pending', 'accepted', 'rejected']]; session.close()"

raw-items-count:
	@echo "📊 Raw Items Report:"
	@PYTHONPATH=$$(pwd) python3 -c "from app.core.store import Store; store = Store('sqlite:///./local.db'); from app.core.models import RawItem; session = store.get_session(); count = session.query(RawItem).count(); print(f'  - Total Raw Items: {count}'); session.close()"

# Quick development workflow
dev: install quick-run
	@echo "🎉 Development environment ready!"

# Visualization
visualize:
	@echo "🔮 Opening event visualization..."
	@cd temp_scripts && python event_visualizer.py && python launch_visualizer.py

# Simple database query
query-simple:
	@echo "🔍 Querying database contents..."
	@cd temp_scripts && python query_database.py

# Comprehensive query commands
query-all:
	@echo "🔍 Comprehensive Database Query - Everything"
	@cd temp_scripts && python query_all.py

query-politics:
	@echo "🏛️ Politics-Related Markets"
	@cd temp_scripts && python query_politics.py

query-crypto:
	@echo "₿ Crypto-Related Markets"
	@cd temp_scripts && python query_crypto.py

query-by-source:
	@echo "📊 Breakdown by Data Source"
	@cd temp_scripts && python query_by_source.py

query-recent:
	@echo "⏰ Recent Items (Last 24 Hours)"
	@cd temp_scripts && python query_recent.py

query-everything:
	@echo "🔍 COMPREHENSIVE DATABASE QUERY - EVERYTHING"
	@cd temp_scripts && python query_everything.py

# Mine prediction markets
mine-markets:
	@echo "⛏️ Mining prediction markets..."
	@cd temp_scripts && python mine_prediction_markets.py --platform both --limit 100 --create-proposals

mine-kalshi:
	@echo "⛏️ Mining Kalshi markets..."
	@cd temp_scripts && python mine_prediction_markets.py --platform kalshi --limit 100 --create-proposals

mine-polymarket:
	@echo "⛏️ Mining Polymarket markets..."
	@cd temp_scripts && python mine_prediction_markets.py --platform polymarket --limit 100 --create-proposals

# Category-specific mining
mine-politics:
	@echo "⛏️ Mining Politics-focused markets..."
	@cd temp_scripts && python mine_prediction_markets.py --platform polymarket --categories "US-current-affairs" --limit 50 --create-proposals

mine-finance:
	@echo "⛏️ Mining Finance/Markets-focused markets..."
	@cd temp_scripts && python mine_prediction_markets.py --platform polymarket --categories "Finance" "Inflation" "Commodity prices" "Forex" --limit 50 --create-proposals

mine-crypto:
	@echo "⛏️ Mining Crypto-focused markets..."
	@cd temp_scripts && python mine_prediction_markets.py --platform both --categories "Crypto" --limit 100 --create-proposals

# Routine Workflows
workflow-scheduler:
	@echo "🔄 Starting workflow scheduler..."
	@PYTHONPATH=$$(pwd) python3 -m app.workflows scheduler

workflow-mining:
	@echo "⛏️ Running market mining workflow..."
	@PYTHONPATH=$$(pwd) python3 -m app.workflows workflow market_mining --platforms kalshi,polymarket --limit 10 --create-proposals

workflow-discovery:
	@echo "🔍 Running discovery workflow..."
	@PYTHONPATH=$$(pwd) python3 -m app.workflows workflow discovery --sources rss,kalshi,polymarket --max-events 10

workflow-prediction:
	@echo "🔮 Running prediction workflow..."
	@PYTHONPATH=$$(pwd) python3 -m app.workflows workflow prediction --max-events 5 --confidence-threshold 0.6

workflow-research:
	@echo "🔬 Running research workflow..."
	@PYTHONPATH=$$(pwd) python3 -m app.workflows workflow research --max-events 3 --depth medium

# Docker commands (if needed)
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t sibyl -f docker/Dockerfile .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run --rm -it sibyl