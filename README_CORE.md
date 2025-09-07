# Sibyl - Core Workflow

A clean, focused prediction market system with a simple **mine → judge** workflow.

## 🎯 Core Workflow

```
External APIs → Mine → Save to Database → Judge & Tag → Save Results
```

## 🚀 Quick Start

### 1. Setup
```bash
# Install dependencies
make install

# Initialize database
make init-db
```

### 2. Run Core Workflow

**Mine Prediction Markets:**
```bash
# Mine both Kalshi and Polymarket
make mine-markets

# Mine specific platforms
make mine-kalshi
make mine-polymarket
```

**Judge Event Proposals:**
```bash
# Judge with LLM (requires API key)
make judge-proposals

# Judge in offline mode (no API key needed)
make judge-offline
```

**Query Results:**
```bash
# Simple database overview
make query-simple

# View event proposals
make query-proposals
```

## 🏗️ Architecture

### Core Components

1. **MarketMiningWorkflow** - Fetches data from Kalshi/Polymarket APIs
2. **EventJudgeAgent** - Evaluates event proposals and assigns tags using LLM
3. **Store** - Database operations for event sourcing
4. **Core Models** - Data models and types

### Data Flow

```
RawItem (from APIs) → EventProposal → Event (after approval)
```

## 🧪 Testing

```bash
# Run core workflow tests
make test-core

# Run all tests
make test

# Run with coverage
make test-coverage
```

## 📁 Clean Structure

### Essential Files
```
app/
├── workflows/market_mining.py    # Core mining
├── agents/judge.py              # Core judging
├── core/store.py                # Database ops
└── adapters/                    # API adapters

temp_scripts/
├── mine_prediction_markets.py   # Mining script
├── judge_event_proposals.py     # Judging script
└── query_*.py                   # Query scripts

tests/
└── test_core_workflow.py        # Core tests
```

### Archived Files
```
archive/experimental_scripts/    # Moved experimental files
```

## 🔧 Development

### Local Development
```bash
# Test the workflow
make test-core

# Run mining
make mine-markets

# Run judging
make judge-proposals

# Check results
make query-simple
```

### CI/CD
- GitHub Actions for automated testing
- Multi-Python version support (3.9, 3.10, 3.11)
- Security checks with Bandit and Safety
- Coverage reporting

## 📚 Documentation

- [Core Workflow Architecture](docs/CORE_WORKFLOW.md) - Detailed architecture guide
- [Makefile Commands](Makefile) - All available commands

## 🎯 Focus

This repository is now focused on the core **mine → judge** workflow:

1. **Mine** prediction markets from external APIs
2. **Save** data to database as RawItems and EventProposals  
3. **Judge** proposals using LLM-based evaluation
4. **Save** judgment results to database

Future extensions (prediction agents, UI) can be added while maintaining this clean foundation.

## 🚀 Next Steps

1. **Deep Research**: Add prediction agents for making predictions
2. **UI Development**: Build user interfaces for the system
3. **Additional Sources**: Add more data source adapters
4. **Advanced Workflows**: Extend with more sophisticated processes

The clean architecture supports all these extensions while maintaining simplicity and maintainability.
