<div align="center">
  <img src="assets/sibyl.jpg" alt="Sibyl - Intelligent Prediction System" width="200" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
</div>

# Sibyl

An intelligent prediction system that mines prediction markets, evaluates events with LLM reasoning, and generates evidence-based predictions with full provenance tracking.

## 🚀 Quick Start

### 1. Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
make init-db
```

### 2. Run Complete Pipeline
```bash
# Full end-to-end workflow: mine → judge → predict → visualize
make run-e2e

# Quick test with limited data
make run-e2e-quick
```

### 3. View Dashboard
```bash
# Start local dashboard server
make serve-dashboard

# Open browser to http://localhost:8080
```

## 🔑 Required Credentials

### Tavily Search API Key (for Research Agent)
- **Required for**: Evidence collection and fact extraction
- **Get it from**: [Tavily API](https://tavily.com/)
- **Set via**: `export TAVILY_API_KEY=your_key_here`
- **Alternative**: Create `.env` file with `TAVILY_API_KEY=your_key_here`

### Google AI API Key (for LLM Agents)
- **Required for**: Event judgment and prediction generation
- **Get it from**: [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Set via**: `export GOOGLE_API_KEY=your_key_here`
- **Alternative**: Create `.env` file with `GOOGLE_API_KEY=your_key_here`

## 🏗️ Business Logic

**Core Workflow: `Mine → Judge → Predict → Visualize`**

1. **Mine** - Fetch prediction markets from Kalshi and Polymarket
2. **Judge** - Evaluate event proposals using LLM-based assessment
3. **Predict** - Generate predictions with research agent and evidence chains
4. **Visualize** - Display results in interactive dashboard

## 📋 Available Commands

### End-to-End Workflows
```bash
make run-e2e              # Complete pipeline: mine → judge → predict → visualize
make run-e2e-quick        # Quick pipeline with limited data
make run-e2e-kalshi       # Pipeline with Kalshi markets only
make run-e2e-polymarket   # Pipeline with Polymarket markets only
```

### Individual Steps
```bash
make step-mine            # Step 1: Mine prediction markets
make step-judge           # Step 2: Judge event proposals
make step-predict         # Step 3: Generate predictions
make step-visualize       # Step 4: Start dashboard
```

### Development & Testing
```bash
make reset-db             # Reset database
make init-db              # Initialize database
make test                 # Run tests
make serve-dashboard      # Start local dashboard server
```

### Database Queries
```bash
make query-db             # Query complete database
make query-simple         # Simple database overview
make query-proposals      # Show event proposals
```

## 🌐 GitHub Pages Dashboard

The system includes a live dashboard with interactive visualizations:

- **Live Demo**: [View Dashboard](https://wwang2.github.io/sibyl/)
- **Features**: 
  - Three-column layout (Events, Predictions, Evidence)
  - Clickable event-prediction relationships
  - Evidence chains with source attribution
  - Real-time data updates
- **Auto-Deploy**: Updates automatically when you push to main branch

### Setup GitHub Pages
1. Go to repository Settings → Pages
2. Source: Deploy from a branch
3. Branch: main, Folder: /docs
4. Save and wait for deployment

## 🔧 Configuration

**Environment Variables:**
```bash
# Required for research agent
TAVILY_API_KEY=your_tavily_key_here

# Required for LLM agents  
GOOGLE_API_KEY=your_google_key_here

# Database
DB_URL=sqlite:///./local.db
```

**Create `.env` file:**
```bash
cat > .env << EOF
# Required: Tavily API Key for evidence collection
TAVILY_API_KEY=your_tavily_key_here

# Required: Google AI API Key for LLM agents
GOOGLE_API_KEY=your_google_key_here

# Database connection
DB_URL=sqlite:///./local.db
EOF
```

## 📁 Project Structure

```
sibyl/
├── app/
│   ├── adapters/          # Kalshi and Polymarket data sources
│   ├── agents/            # LLM agents (judge, research)
│   ├── core/              # Database, models, types
│   ├── workflows/         # Main business logic workflows
│   └── cli.py             # Command-line interface
├── docs/                  # GitHub Pages dashboard
│   ├── index.html         # Main dashboard
│   ├── data/              # Exported prediction data
│   └── serve.py           # Local server
├── temp_scripts/          # Development utilities
├── tests/                 # Test suite
└── Makefile              # Development commands
```

## 🧪 Testing

**Run Tests:**
```bash
make test                 # Run all tests
```

**Development Workflow:**
```bash
make reset-db             # Clean start
make run-e2e-quick        # Test pipeline
make serve-dashboard      # View results
```

## 📊 Database Schema

- `raw_items` - Raw data from prediction markets
- `event_proposals` - Generated event proposals
- `events` - Confirmed events with states
- `predictions` - LLM-generated predictions
- `prediction_attributions` - Evidence source tracking
- `workflow_runs` - Execution logs
- `tool_calls` - Research agent tool usage

## 🔄 Development Workflow

1. **Setup**: `make init-db`
2. **Test Pipeline**: `make run-e2e-quick`
3. **View Results**: `make serve-dashboard`
4. **Reset**: `make reset-db` (for clean testing)

## 📝 License

MIT License