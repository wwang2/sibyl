
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
	@echo ""
	@echo "Agentic Workflows:"
	@echo "  quick-run        Quick agentic workflow (1 feed, 3 items, 2 events)"
	@echo "  quick-offline    Quick offline workflow with test fixtures (no network)"
	@echo "  run-full         Full agentic workflow without limits"
	@echo "  run-offline      Offline workflow using test fixtures (no network)"
	@echo "  test-workflow    Test the complete event sourcing workflow"
	@echo ""
	@echo "End-to-End Prediction Pipeline:"
	@echo "  run-e2e          Complete pipeline: reset → mine → judge → predict → visualize"
	@echo "  run-e2e-quick    Quick pipeline with limited data"
	@echo "  run-e2e-kalshi   Pipeline with Kalshi markets only"
	@echo "  run-e2e-polymarket Pipeline with Polymarket markets only"
	@echo "  step-mine        Step 1: Mine prediction markets only"
	@echo "  step-judge       Step 2: Judge event proposals only"
	@echo "  step-predict     Step 3: Run enhanced predictions only"
	@echo "  step-visualize   Step 4: Start visualization dashboard"
	@echo ""
	@echo "Testing & Development:"
	@echo "  test             Run all tests"
	@echo "  test-core        Run core workflow tests only"
	@echo "  test-unit        Run unit tests"
	@echo "  test-integration Run integration tests"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  lint             Run linting checks"
	@echo ""
	@echo "Database Query Tools:"
	@echo "  query-db         Query complete database (all tables)"
	@echo "  query-simple     Simple database query with counts and recent items"
	@echo "  query-proposals  Show event proposals with status breakdown"
	@echo ""
	@echo "Prediction Market Mining:"
	@echo "  mine-markets     Mine both Kalshi and Polymarket (100 markets each)"
	@echo "  mine-kalshi      Mine Kalshi prediction markets only"
	@echo "  mine-polymarket  Mine Polymarket prediction markets only"
	@echo ""
	@echo "Event Proposal Judgment:"
	@echo "  judge-proposals  Judge event proposals using LLM-based evaluation"
	@echo "  judge-offline    Judge proposals in offline mode (no LLM calls)"
	@echo "  judge-sample     Judge a sample of 10 proposals for testing"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Clean up temporary files and caches"
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

test-core:
	@echo "🔧 Running core workflow tests..."
	PYTHONPATH=$$(pwd) python3 -m pytest tests/test_core_workflow.py -v

test-unit:
	@echo "🔬 Running unit tests..."
	PYTHONPATH=$$(pwd) python3 -m pytest tests/ -m "unit" -v

test-integration:
	@echo "🔗 Running integration tests..."
	PYTHONPATH=$$(pwd) python3 -m pytest tests/ -m "integration" -v

test-coverage:
	@echo "📊 Running tests with coverage..."
	PYTHONPATH=$$(pwd) python3 -m pytest tests/ --cov=app --cov-report=html --cov-report=term

# Enhanced Prediction Workflow
run-enhanced-prediction:
	@echo "🔮 Running enhanced prediction workflow with research agent..."
	PYTHONPATH=$$(pwd) python3 temp_scripts/test_enhanced_prediction.py

view-dashboard:
	@echo "🌐 Opening prediction dashboard..."
	@open docs/index.html 2>/dev/null || xdg-open docs/index.html 2>/dev/null || echo "Please open docs/index.html in your browser"

serve-dashboard:
	@echo "🚀 Starting local server for prediction dashboard..."
	@echo "📊 Make sure to run 'make run-enhanced-prediction' first to generate data"
	@cd docs && python3 serve.py

# End-to-End Workflow (Modular)
run-e2e:
	@echo "🚀 Running complete end-to-end prediction workflow..."
	@echo "   This will: reset DB → mine markets → judge proposals → run predictions → visualize"
	@make reset-db
	@make mine-markets
	@make judge-proposals
	@make run-enhanced-prediction
	@echo "✅ End-to-end workflow completed! Run 'make serve-dashboard' to view results."

run-e2e-quick:
	@echo "⚡ Running quick end-to-end workflow (limited data)..."
	@make reset-db
	@make mine-kalshi
	@make judge-sample
	@make run-enhanced-prediction
	@echo "✅ Quick end-to-end workflow completed! Run 'make serve-dashboard' to view results."

run-e2e-kalshi:
	@echo "⛏️ Running end-to-end workflow with Kalshi only..."
	@make reset-db
	@make mine-kalshi
	@make judge-proposals
	@make run-enhanced-prediction
	@echo "✅ Kalshi end-to-end workflow completed! Run 'make serve-dashboard' to view results."

run-e2e-polymarket:
	@echo "⛏️ Running end-to-end workflow with Polymarket only..."
	@make reset-db
	@make mine-polymarket
	@make judge-proposals
	@make run-enhanced-prediction
	@echo "✅ Polymarket end-to-end workflow completed! Run 'make serve-dashboard' to view results."

# Individual workflow steps (using existing commands)
step-mine:
	@echo "⛏️ Step 1: Mining prediction markets..."
	@make mine-markets

step-judge:
	@echo "⚖️ Step 2: Judging event proposals..."
	@make judge-proposals

step-create-events:
	@echo "🎯 Step 3: Creating events from approved proposals..."
	@make create-events

step-predict:
	@echo "🔮 Step 4: Running enhanced predictions..."
	@make run-enhanced-prediction

step-visualize:
	@echo "📊 Step 5: Visualizing results..."
	@make serve-dashboard

# Database Query Tools
query-db:
	@echo "🔍 Querying complete database..."
	@PYTHONPATH=$$(pwd) python3 temp_scripts/query_database.py


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


# Simple database query
query-simple:
	@echo "🔍 Querying database contents..."
	@cd temp_scripts && python query_database.py


query-proposals:
	@echo "🎯 Event Proposals Status Report"
	@cd temp_scripts && python query_proposals_simple.py

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


# Event Proposal Judgment
judge-proposals:
	@echo "⚖️ Judging event proposals using LLM-based evaluation..."
	@cd temp_scripts && python judge_event_proposals.py --status-filter pending

judge-offline:
	@echo "⚖️ Judging event proposals in offline mode..."
	@cd temp_scripts && python judge_event_proposals.py --offline --status-filter pending

judge-sample:
	@echo "⚖️ Judging sample of 10 event proposals..."
	@cd temp_scripts && python judge_event_proposals.py --max-proposals 10 --status-filter pending

# Create events from approved proposals
create-events:
	@echo "🎯 Creating events from approved proposals..."
	@cd temp_scripts && python create_events_from_proposals.py


# Docker commands (if needed)
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t sibyl -f docker/Dockerfile .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run --rm -it sibyl