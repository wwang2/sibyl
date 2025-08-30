<file name=0 path=/Users/wujiewang/projects/signal_loom/spec.md># Sibyl: Agentic Event Discovery — Minimal Viable Spec (v2)

**Vision:** Start *small but durable*. Ship a working agentic backbone that discovers predictable events and assigns likelihoods, with provenance. Make choices that can grow into a fullstack web service later (Cloud Run + Postgres + UI).

---

## 1) Scope (Now vs Later)

**Now (MVP)**  
- Two agents: **Discovery** (gathers candidate signals) and **Assessor** (evidence → likelihood p, TTC).  
- Minimal persistence with provenance (Prediction ↔ Evidence ↔ AgentRun).  
- Runnable locally and on Cloud Run via Docker.  
- Google AI SDK (API key) for LLM calls.

**Later (Next Phases)**  
- Postgres/Cloud SQL, Pub/Sub, BigQuery, pgvector.  
- Online benchmark + calibration dashboards.  
- Web app (auth, feeds, explanations).

---

## 2) Repo Structure

```
agentic-event-discovery/
├─ README.md
├─ spec.md
├─ .env.example
├─ requirements.txt
├─ docker/
│  ├─ Dockerfile
│  └─ entrypoint.sh
├─ app/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ adapters/
│  │  └─ rss.py
│  ├─ core/
│  │  ├─ types.py
│  │  ├─ store.py
│  │  ├─ edl_light.py
│  │  └─ hashing.py
│  ├─ llm/
│  │  └─ adk_client.py
│  ├─ agents/
│  │  ├─ discovery.py
│  │  └─ assessor.py
│  ├─ run_cycle.py            # discovery -> assess once
│  └─ cli.py                  # optional: typer wrapper
└─ tests/
   └─ test_smoke.py
```

Design rules: one small package (**app/**) with clear subfolders; one entrypoint (**run_cycle.py**). Add modules only when needed.

---

## 3) Dependencies (tight set)

`requirements.txt`
```
pydantic>=2.7,<3
pydantic-settings>=2.2,<3
typer>=0.12,<1
httpx>=0.27,<1
feedparser>=6,<7
tenacity>=8.3,<9
sqlalchemy>=2,<3
sqlite-utils>=3.36,<4
orjson>=3.10,<4
google-generativeai>=0.7,<1
pytest>=8,<9
```

`.env.example`
```
GOOGLE_API_KEY=your_key
DB_URL=sqlite:///./local.db
MODEL=gemini-1.5-flash
SOURCES=rss,prwires,edgar
RUN_MODE=local
LLM_MODE=live   # live | mock
MOCK_SEED=42
```

---

## 4) Docker (Cloud Run-friendly)

`docker/Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl tini && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/usr/bin/tini","--","/entrypoint.sh"]
CMD ["python","-m","app.run_cycle"]
```

`docker/entrypoint.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail
[[ -f ".env" ]] && export $(grep -v '^#' .env | xargs) || true
exec "$@"
```

---

## 5) Data Model (provenance-first, simple)

Tables (SQLite now; same schema works in Postgres):
- **evidence**(id, source_type, url, title, snippet, content_hash, first_seen_at, fetched_at, meta_json)
- **proto_events**(id, key, state, first_seen_at, last_update_at)
- **predictions**(id, proto_event_id, p, ttc_hours, rationale, created_at)
- **agent_runs**(id, agent_type, input_json, output_json, tokens_in, tokens_out, cost_usd, latency_ms, started_at, ended_at)
- **prediction_evidence**(prediction_id, evidence_id, rank)

Keep reasoning minimal and internal; expose safe explanations later.

---

## 6) Agents (what they actually do)

**DiscoveryAgent**
1. Pull from sources (rss/prwires/edgar).
2. Normalize → `content_hash` / dedupe.
3. Group into `proto_events` by canonical key.
4. Persist `evidence` + `proto_events` + `agent_run`.
5. Enqueue new/updated events for assessment (function call in MVP).

**AssessorAgent**
- Gather recent evidence for a proto_event.
- Call Gemini via `adk_client.reason_prediction()`.
- Return JSON: `{p, ttc_hours, rationale, used_evidence_ids}`.
- Persist `prediction` and link to evidence.

---

## 7) Orchestration & CLI

- **Local:** `python -m app.run_cycle  # runs discovery then assessment once`  
  `--loop` note to be handled by CLI later.  
- **Cloud Run:** container runs `app.run_cycle` once per invocation; use Cloud Scheduler to trigger every N minutes.

CLI examples:
```
python -m app.run_cycle
agent run-cycle --all         # optional Typer wrapper around run_cycle
```

---

## 8) Local development & testing pattern

**Goal:** Make it trivial for you (or a Coding AI) to run, test, and iterate fully offline/locally, and only flip to live LLM/data when ready.

### 8.1 Setup

```bash
# 1) Create env and install deps (uv or venv + pip)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Local env
cp .env.example .env   # edit DB_URL / GOOGLE_API_KEY if needed

# 3) Initialize local DB (tables)
python - <<'PY'
from app.core.store import Store
s = Store.from_env(); s.create_all()
print('DB initialized at', s.engine.url)
PY
```

### 8.2 Run locally (two modes)

- **Mock mode (offline, deterministic)**
  - `.env`: `LLM_MODE=mock` and optional `MOCK_SEED=42`.
  - `adk_client.py` returns deterministic `{p, ttc_hours, rationale}` based on seed and evidence length.
  - Great for CI and unit tests without network/keys.

```bash
export LLM_MODE=mock
python -m app.run_cycle
```

- **Live mode (calls Gemini)**
  - `.env`: `LLM_MODE=live`, `GOOGLE_API_KEY=...`.

```bash
export LLM_MODE=live
python -m app.run_cycle
```

### 8.3 Testing strategy (pytest)

**Test types**
- **Unit**: hashing, grouping, store persistence, and adapter parsing.
- **Integration**: a single `run_cycle` against fixture feeds; assert rows in `evidence`, `proto_events`, `predictions` and the linking table.

**Fixtures layout**
```
tests/
├─ fixtures/
│  ├─ rss_sample.xml
│  └─ rss_empty.xml
└─ test_smoke.py
```

**Mocking LLM**
```python
# tests/test_smoke.py
import os
from app.run_cycle import main

def test_run_cycle_mock(tmp_path, monkeypatch):
    monkeypatch.setenv('LLM_MODE','mock')
    os.environ['DB_URL'] = f'sqlite:///{tmp_path}/test.db'
    # Optionally redirect adapters to fixture file paths
    monkeypatch.setenv('RSS_FIXTURE','tests/fixtures/rss_sample.xml')
    main()
```

**Mocking adapters** (no network)
```python
# Example: inside app/adapters/rss.py, if env RSS_FIXTURE is set, read from file
import os, pathlib

def fetch(...):
    fixture = os.getenv('RSS_FIXTURE')
    if fixture:
        text = pathlib.Path(fixture).read_text()
        return parse_rss_text(text)
    # else: perform normal HTTP fetch
```

### 8.4 Developer ergonomics

- **Scripts** (optional):
  - `scripts/dev_db_reset.sh` → drop & recreate local DB.
  - `scripts/run_local.sh` → export envs and run `python -m app.run_cycle`.
- **Lint/type** (optional now, recommended soon): ruff, mypy.
- **Determinism**: use `MOCK_SEED` and fixed fixture files so CI is stable.
- **Observability**: print minimal counters at end of `run_cycle` (e.g., evidence count, predictions emitted). This doubles as a smoke check.

### 8.5 What to test first

1) **Store.create_all()** creates all tables on empty DB.
2) **RSS adapter** parses a small `rss_sample.xml` and yields at least 1 evidence.
3) **Run cycle (mock LLM)** emits a prediction and links it to evidence.
4) **Idempotency**: running twice with same fixture does not duplicate evidence (via `content_hash` dedupe).

---

## 9) Telemetry (minimal)

- JSON logs per agent_run (agent_type, edl_name, tokens, cost, latency, errors).  
- Counters (in logs): `evidence_ingested`, `predictions_emitted`.  
- Add OpenTelemetry/Cloud Monitoring later if needed.

---

## 10) Milestones (keep it moving)

- **M1:** Repo + Docker + SQLite store + RSS adapter + one EDL.  
- **M2:** DiscoveryAgent end‑to‑end (dedupe + proto_events).  
- **M3:** AssessorAgent via Gemini; predictions linked to evidence.  
- **M4:** Cloud Run deploy + Scheduler; smoke test + first daily runs.

**Exit to Fullstack:** When M4 runs reliably for 1–2 weeks, add Postgres, pgvector, and a simple web UI (Next.js or Flask+HTMX) to browse proto_events, predictions, and evidence with explanations.

---

## 11) References

- [Google Generative AI SDK (Python)](https://cloud.google.com/generative-ai/docs/sdk/quickstart) — Official Python SDK for Google Generative AI  
- [ADK Documentation](https://cloud.google.com/generative-ai/docs/adk) — Agent Development Kit docs for building AI agents  
- [Cloud Run](https://cloud.google.com/run/docs) — Serverless container platform on Google Cloud  
- [Cloud Scheduler](https://cloud.google.com/scheduler/docs) — Managed cron job service on Google Cloud  
- [SEC EDGAR API](https://www.sec.gov/edgar/sec-api-documentation) — Official SEC EDGAR API documentation  
- [feedparser](https://feedparser.readthedocs.io/en/latest/) — Python library for parsing RSS and Atom feeds  
- [httpx](https://www.python-httpx.org/) — HTTP client for Python with sync and async support  
- [SQLAlchemy](https://docs.sqlalchemy.org/en/20/) — Python SQL toolkit and Object Relational Mapper  
- [Pydantic Settings](https://pydantic.dev/latest/usage/settings/) — Configuration management with Pydantic  
- [Typer](https://typer.tiangolo.com/) — Library for building CLI applications in Python  
- [OpenTelemetry](https://opentelemetry.io/docs/instrumentation/python/) — Observability framework for cloud-native software instrumentation
</file>
