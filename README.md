<div align="center">
  <img src="assets/sibyl.jpg" alt="Sibyl - Agentic Event Discovery System" width="200" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
</div>

# Sibyl

An agentic event discovery system that discovers predictable events and assigns likelihoods with full provenance tracking.

## 🚀 Quick Start

### 1. Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
make init-db
```

### 2. Run (Choose One)

**Offline Mode (No API Key Required):**
```bash
make run-offline
```

**Live Mode (Requires Google API Key):**
```bash
# Set your Google AI API key
export GOOGLE_API_KEY=your_api_key_here
make quick-run
```

## 🔑 Required Credentials

### Google AI API Key (for live mode)
- **Required for**: LLM-powered predictions and assessments
- **Get it from**: [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Set via**: `export GOOGLE_API_KEY=your_key_here`
- **Alternative**: Create `.env` file with `GOOGLE_API_KEY=your_key_here`

## 📋 Available Commands

### Development
```bash
make help              # Show all available commands
make quick-run         # Quick test (1 feed, 3 items, 1 event)
make run-offline       # Offline test with fixtures
make reset-db          # Reset database
make dev-reset         # Reset DB + quick run
```

### Testing
```bash
make test              # Run tests
make run-offline       # Test without network
```

## 🏗️ System Architecture

**Two Main Agents:**
- **Discovery Agent**: Gathers evidence from RSS feeds
- **Assessor Agent**: Uses Google Gemini to evaluate evidence and make predictions

**Key Features:**
- RSS feed parsing with network resilience
- Content deduplication via SHA-256 hashing
- SQLite database with full provenance
- Offline mode for development/testing
- Docker support for deployment

## 🔧 Configuration

**Environment Variables:**
- `GOOGLE_API_KEY` - **Required for live mode** - Your Google AI API key
- `LLM_MODE` - `live` (default) or `mock` for testing
- `DB_URL` - Database connection (default: `sqlite:///./local.db`)
- `MODEL` - Gemini model (default: `gemini-1.5-flash`)

**Create `.env` file:**
```bash
# Copy and edit this template
cat > .env << EOF
# REQUIRED: Google AI API Key for live mode
# Get your API key from: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your_api_key_here

# LLM Mode: 'live' for real API calls, 'mock' for testing
LLM_MODE=live

# Database connection string
DB_URL=sqlite:///./local.db

# Gemini model to use
MODEL=gemini-1.5-flash
EOF
```

## 🌐 GitHub Pages

The project includes a GitHub Pages website with dynamic visualizations and old-school styling:

- **Live Demo**: [View the website](https://yourusername.github.io/sibyl) (replace with your GitHub username)
- **Features**: Interactive charts, real-time system status, old-school Times New Roman design
- **Auto-Deploy**: Automatically updates when you push to the main branch

### Setup GitHub Pages

1. **Enable Pages**: Go to repository Settings → Pages → Source: GitHub Actions
2. **Push changes**: The website will deploy automatically
3. **Access site**: Available at `https://yourusername.github.io/sibyl`

**Troubleshooting**: See `docs/SETUP.md` for detailed setup instructions.

## 🐳 Docker

```bash
# Build and run
docker build -f docker/Dockerfile -t sibyl .
docker run --env-file .env sibyl
```

## 📁 Project Structure

```
sibyl/
├── app/
│   ├── adapters/          # RSS and other data sources
│   ├── agents/            # Discovery and Assessor agents
│   ├── core/              # Database, types, utilities
│   ├── llm/               # Google AI SDK client
│   └── cli.py             # Command-line interface
├── docs/                  # GitHub Pages website
├── tests/                 # Tests and fixtures
├── docker/                # Docker configuration
└── Makefile              # Development commands
```

## 🧪 Testing

**Smoke Test:**
```bash
pytest tests/test_smoke.py -v
```

**Offline Development:**
```bash
make run-offline  # Uses test fixtures, no network required
```

## 📊 Database Schema

- `evidence` - Raw evidence from data sources
- `proto_events` - Grouped events awaiting assessment  
- `predictions` - LLM-generated predictions with probabilities
- `agent_runs` - Execution logs for all agent runs
- `llm_interactions` - Detailed LLM call tracking

## 🔄 Development Workflow

1. **Start with offline mode**: `make run-offline`
2. **Add your API key**: `export GOOGLE_API_KEY=your_key`
3. **Test live mode**: `make quick-run`
4. **Reset for clean testing**: `make dev-reset`

## 📝 License

MIT License