# Core Workflow Architecture

This document describes the clean, focused architecture of the Sybil prediction system, centered around the core **mine → judge** workflow.

## Overview

The system follows a simple, maintainable workflow:

```
External APIs → Mine → Save to Database → Judge → Save Results
```

## Core Components

### 1. Market Mining (`MarketMiningWorkflow`)

**Location**: `app/workflows/market_mining.py`

**Purpose**: Fetches prediction market data from external APIs and saves to database.

**Key Features**:
- Fetches data from Kalshi and Polymarket APIs
- Saves raw market data as `RawItem` entities
- Creates `EventProposal` entities from market data
- Configurable platforms, categories, and limits

**Usage**:
```bash
# Mine both platforms
make mine-markets

# Mine specific platform
make mine-kalshi
make mine-polymarket

# Via CLI
python -m app.workflows workflow market_mining --platforms kalshi,polymarket
```

### 2. Event Judge (`EventJudgeAgent`)

**Location**: `app/agents/judge.py`

**Purpose**: Evaluates event proposals using LLM-based assessment.

**Key Features**:
- LLM-powered evaluation of event proposals
- Scoring on multiple criteria (answerability, significance, frequency, temporal relevance)
- **Consolidated tagging**: Assigns categories (politics, economics, crypto, etc.) during judgment
- Offline mode for testing without LLM calls
- Saves judgment results and tags to database

**Usage**:
```bash
# Judge proposals with LLM
make judge-proposals

# Judge in offline mode
make judge-offline

# Via CLI
python -m app.workflows workflow judge --max-proposals 10
```

### 3. Database Store (`Store`)

**Location**: `app/core/store.py`

**Purpose**: Centralized database operations for the event sourcing system.

**Key Features**:
- Event sourcing data flow: `RawItem` → `EventProposal` → `Event`
- Full workflow run tracking with `WorkflowRun` and `ToolCall`
- Prediction attribution to raw items
- Market listing integration

### 4. Core Models

**Location**: `app/core/models.py`, `app/core/types.py`

**Purpose**: Data models and types for the system.

**Key Entities**:
- `RawItem`: Raw data from external sources
- `EventProposal`: Candidate events for evaluation
- `Event`: Canonical events after approval
- `WorkflowRun`: Complete reasoning traces
- `Prediction`: Predictions with full attribution

## Data Flow

### 1. Mining Phase
```
External APIs (Kalshi/Polymarket) 
    ↓
MarketMiningWorkflow
    ↓
RawItem (saved to database)
    ↓
EventProposal (created from RawItem)
```

### 2. Judging Phase
```
EventProposal (PENDING status)
    ↓
EventJudgeAgent (LLM evaluation + tagging)
    ↓
Judgment (scores + reasoning + tags)
    ↓
EventProposal (status updated: ACCEPTED/REJECTED/PENDING + tagged)
```

### 3. Database Schema
```
RawItem (source data)
    ↓
EventProposal (candidate events)
    ↓
Event (approved events)
    ↓
WorkflowRun (prediction workflows)
    ↓
Prediction (with attributions)
```

## Configuration

### Mining Configuration
```python
config = MiningConfig(
    platforms=["kalshi", "polymarket"],
    categories=["Politics", "Economics", "Technology"],
    limit_per_category=20,
    create_proposals=True,
    database_url="sqlite:///./local.db"
)
```

### Judge Configuration
```python
agent = EventJudgeAgent(
    store=store,
    model_name="gemini-1.5-flash-8b",
    approval_threshold=0.7,
    offline_mode=False
)
```

## Testing

### Unit Tests
```bash
# Run core workflow tests
make test-core

# Run all tests
make test

# Run with coverage
make test-coverage
```

### Test Structure
- `tests/test_core_workflow.py`: Comprehensive tests for core components
- Tests cover: mining, judging, database operations, integration
- Offline mode testing for development without LLM calls

## CI/CD Pipeline

### GitHub Actions
- **Test**: Multi-Python version testing (3.9, 3.10, 3.11)
- **Core Workflow Test**: Specific tests for mine→judge workflow
- **Security**: Bandit and Safety checks
- **Build**: Documentation and artifact generation

### Local Development
```bash
# Install dependencies
make install

# Run core workflow
make mine-markets
make judge-proposals

# Query results
make query-simple
make query-proposals
```

## File Organization

### Core Files (Essential)
```
app/
├── workflows/
│   └── market_mining.py          # Core mining workflow
├── agents/
│   └── judge.py                  # Core judging agent
├── core/
│   ├── store.py                  # Database operations
│   ├── models.py                 # Data models
│   └── types.py                  # Type definitions
└── adapters/
    ├── kalshi.py                 # Kalshi API adapter
    └── polymarket.py             # Polymarket API adapter

temp_scripts/
├── mine_prediction_markets.py    # Mining script
├── judge_event_proposals.py      # Judging script
├── query_database.py             # Database queries
└── query_proposals_simple.py     # Proposal queries

tests/
└── test_core_workflow.py         # Core workflow tests
```

### Archived Files (Experimental)
```
archive/
└── experimental_scripts/         # Moved experimental files
    ├── event_visualizer.py
    ├── query_*.py (specialized)
    ├── test_*.py (old tests)
    └── *.md (documentation)
```

## Development Workflow

### 1. Local Development
```bash
# Setup
make install

# Test core workflow
make test-core

# Run mining
make mine-markets

# Run judging
make judge-proposals

# Query results
make query-simple
```

### 2. Testing
```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration

# Check coverage
make test-coverage
```

### 3. CI/CD
- Push to `main` or `develop` triggers full CI pipeline
- Tests run on multiple Python versions
- Security checks with Bandit and Safety
- Coverage reporting

## Future Extensions

The clean architecture supports easy extension:

1. **Prediction Agents**: Add to `app/agents/` for making predictions
2. **UI Components**: Add to `app/ui/` for user interfaces
3. **Additional Adapters**: Add to `app/adapters/` for new data sources
4. **Workflow Extensions**: Add to `app/workflows/` for new processes

## Maintenance

### Regular Tasks
- Run tests: `make test`
- Check security: `make lint`
- Update dependencies: `pip install -r requirements.txt`
- Clean up: `make clean`

### Monitoring
- Database queries: `make query-simple`
- Proposal status: `make query-proposals`
- Test coverage: `make test-coverage`

This architecture provides a solid foundation for the core mine→judge workflow while maintaining simplicity and extensibility for future development.
