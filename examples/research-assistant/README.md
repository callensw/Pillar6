# Pillar6 Reference App: Multi-Agent Research Assistant

A complete demonstration of all six Pillar6 pillars working together in a
multi-agent system. Give it a research question and a team of AI agents
autonomously researches, analyses, and produces a structured report.

## Architecture

```
User Question
    │
    ▼
┌─────────────┐
│  Conductor   │  ← Supervisor agent, orchestrates the team
│  (Sonnet)    │
└─────┬───────┘
      │ Delegates to:
      ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Researcher  │  │  Researcher  │  │  Analyst     │
│  Agent #1    │  │  Agent #2    │  │  Agent       │
│  (Haiku)     │  │  (Haiku)     │  │  (Sonnet)    │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       ▼                ▼                ▼
   Web Search       Web Search      Synthesis +
   + Extract        + Extract       Final Report
```

**Pillar usage:**
- **Context Management** — Each agent has its own token budget and priority buckets
- **Tool Orchestration** — web_search with retries, read_url, format_report, add_citation
- **Security** — Per-agent tool permissions (researchers can't format, analyst can't search)
- **Routing** — Conductor/analyst use Sonnet, researchers use Haiku
- **Observability** — Full tracing, cost tracking, real-time event streaming
- **Evaluation** — Dataset-driven eval with scoring and comparison

## Quick Start

### Prerequisites

```bash
pip install -e "../../[dev]"    # Install pillar6 from source
pip install fastapi uvicorn     # For server mode
```

### CLI Mode

```bash
cd examples/research-assistant
PYTHONPATH=../../:. python main.py "What are the latest developments in quantum computing?"
```

### Interactive Mode

```bash
PYTHONPATH=../../:. python main.py --interactive
```

### Server Mode (for Dashboard)

```bash
PYTHONPATH=../../:. python main.py --serve
# API available at http://127.0.0.1:8000
```

### Run the Dashboard

```bash
cd dashboard
npm install
npm run dev
# Open http://localhost:5173
```

### Run Evaluation

```bash
PYTHONPATH=../../:. python eval/run_eval.py
```

### Run Tests

```bash
PYTHONPATH=../../:. python -m pytest tests/ -v
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | No | Supabase project URL for persistent storage |
| `SUPABASE_KEY` | No | Supabase anon/service key |

If Supabase is not configured, the app uses in-memory storage (data lost on restart).

## Supabase Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run `schema.sql` in the SQL editor
3. Set `SUPABASE_URL` and `SUPABASE_KEY` environment variables

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/research` | Submit a research question |
| `GET` | `/research/:id` | Get job status and results |
| `GET` | `/research/:id/trace` | Get observability trace |
| `GET` | `/research/:id/costs` | Get cost breakdown |
| `GET` | `/jobs` | List recent research jobs |
| `GET` | `/system` | System health and statistics |
| `WS` | `/ws/:id` | Real-time event stream |

## Deploying the Dashboard

```bash
cd dashboard
npm run build

# Deploy to Vercel
npx vercel --prod
```

Set `VITE_API_URL` to your API server URL before building for production.

## Project Structure

```
examples/research-assistant/
├── main.py              # CLI / interactive / server entry point
├── config.py            # Pillar6 configuration for each agent
├── agents.py            # Agent assembly and tool registration
├── pipeline.py          # Research pipeline orchestration
├── server.py            # FastAPI server with WebSocket
├── storage.py           # Supabase + in-memory storage
├── schema.sql           # Supabase table definitions
├── tools/               # Tool implementations
│   ├── web_search.py    # Mock web search (swap for real API)
│   ├── read_url.py      # Mock URL reader
│   ├── format_report.py # Markdown report formatter
│   └── add_citation.py  # Footnote citation tool
├── tests/               # Reference app tests
├── eval/                # Evaluation dataset and runner
│   ├── dataset.json     # 10 research questions
│   └── run_eval.py      # Eval runner script
└── dashboard/           # React + TypeScript dashboard
    ├── src/
    └── package.json
```
