# Sibyl

A minimal viable implementation of an agentic event discovery system that discovers predictable events and assigns likelihoods with provenance.

## Overview

This system consists of two main agents:
- **Discovery Agent**: Gathers candidate signals from various sources (RSS feeds, etc.)
- **Assessor Agent**: Evaluates evidence and makes predictions using Google's Gemini AI

## Features

- RSS feed parsing and evidence gathering
- Content deduplication using SHA-256 hashing
- Proto event grouping and management
- LLM-powered prediction assessment
- SQLite database with full provenance tracking
- Mock mode for offline testing
- Docker support for Cloud Run deployment

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 2. Initialize Database

```bash
python - <<'PY'
from app.core.store import Store
s = Store.from_env()
s.create_all()
print('DB initialized at', s.engine.url)
PY
```

### 3. Run in Mock Mode (Offline)

```bash
export LLM_MODE=mock
python -m app.run_cycle
```

### 4. Run in Live Mode (Requires API Key)

```bash
export LLM_MODE=live
export GOOGLE_API_KEY=your_api_key_here
python -m app.run_cycle
```

## Testing

Run the smoke tests:

```bash
pytest tests/test_smoke.py -v
```

## Docker

Build and run with Docker:

```bash
# Build image
docker build -f docker/Dockerfile -t signal-loom .

# Run with environment file
docker run --env-file .env signal-loom
```

## Project Structure

```
signal_loom/
├── app/
│   ├── adapters/          # Data source adapters (RSS, etc.)
│   ├── agents/            # Discovery and Assessor agents
│   ├── core/              # Core types, store, and utilities
│   ├── llm/               # LLM client (Google AI SDK)
│   ├── config.py          # Configuration management
│   └── run_cycle.py       # Main orchestration
├── tests/                 # Test files and fixtures
├── docker/                # Docker configuration
└── requirements.txt       # Python dependencies
```

## Configuration

Key environment variables:

- `GOOGLE_API_KEY`: Your Google AI API key
- `DB_URL`: Database connection string (default: sqlite:///./local.db)
- `LLM_MODE`: `live` or `mock` (default: live)
- `MODEL`: Gemini model to use (default: gemini-1.5-flash)
- `RSS_FIXTURE`: Path to RSS fixture file for testing

## Database Schema

The system uses SQLite with the following tables:

- `evidence`: Raw evidence from data sources
- `proto_events`: Grouped events awaiting assessment
- `predictions`: LLM-generated predictions with probabilities
- `agent_runs`: Execution logs for all agent runs
- `prediction_evidence`: Links between predictions and evidence

## Development

### Adding New Data Sources

1. Create a new adapter in `app/adapters/`
2. Implement the fetch and parse methods
3. Update the Discovery agent to use the new adapter

### Customizing LLM Prompts

Modify the prompt in `app/llm/adk_client.py` in the `_live_reason_prediction` method.

### Adding New Agent Types

1. Create a new agent class in `app/agents/`
2. Add the agent type to the `AgentType` enum in `app/core/types.py`
3. Update the orchestration logic in `app/run_cycle.py`

## Next Steps

This implementation provides the foundation for a full-stack event discovery system. Future enhancements could include:

- PostgreSQL and pgvector for better scalability
- Web UI for browsing predictions and evidence
- Real-time event streaming
- Advanced ML models for prediction calibration
- Integration with more data sources (SEC EDGAR, PR wires, etc.)

## License

MIT License
