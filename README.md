# Talent Promo

AI-powered resume optimization platform that helps talent present themselves effectively for target job opportunities.

## Overview

Talent Promo uses an agentic workflow to analyze your profile and a target job posting, then guides you through an intelligent Q&A interview to create an ATS-optimized resume tailored specifically for that role.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Input Step  │→ │Research View│→ │  Q&A Chat   │→ │  Tiptap Editor     │ │
│  │ (URLs)      │  │ (Progress)  │  │ (Interview) │  │  (Resume Canvas)   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │ SSE Stream
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Backend (FastAPI)                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         LangGraph Workflow                            │   │
│  │                                                                       │   │
│  │  [fetch_profile] → [fetch_job] → [research] → [analyze]              │   │
│  │                                                     │                 │   │
│  │                                                     ▼                 │   │
│  │  [export] ← [editor_assist] ← [draft_resume] ← [qa_node]             │   │
│  │                                                  ↻ interrupt()        │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   EXA API       │  │  Anthropic API  │  │  Checkpointer               │  │
│  │   (Web Search)  │  │  (Claude LLM)   │  │  (Postgres/Redis/Memory)    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Workflow

1. **Ingest**: Fetch LinkedIn profile or parse uploaded resume + fetch target job posting
2. **Research**: Research company culture, tech stack, and similar employees using EXA
3. **Analysis**: Identify gaps and recommend what to highlight
4. **Q&A Interview**: Human-in-the-loop interview (up to 10 rounds) to gather additional context
5. **Draft Resume**: Generate ATS-optimized resume tailored to the role
6. **Editor Assist**: AI-powered editing in Tiptap canvas
7. **Export**: Export to DOCX or PDF

## Project Structure

```
talent-promo/
├── apps/
│   ├── web/                    # Next.js frontend
│   │   ├── app/
│   │   │   ├── optimize/       # Resume optimization wizard
│   │   │   ├── components/     # React components
│   │   │   └── hooks/          # Custom React hooks
│   │   └── package.json
│   │
│   └── api/                    # FastAPI backend
│       ├── langgraph/          # LangGraph workflow
│       │   ├── graph.py        # Main workflow definition
│       │   ├── state.py        # State schemas with memory hierarchy
│       │   ├── context.py      # Context management utilities
│       │   └── nodes/          # Workflow nodes
│       │       ├── ingest.py
│       │       ├── research.py
│       │       ├── analysis.py
│       │       ├── qa.py
│       │       ├── drafting.py
│       │       ├── editor.py
│       │       └── export.py
│       ├── routers/
│       │   └── optimize.py     # API endpoints
│       ├── tools/
│       │   └── exa_tool.py     # EXA search tools
│       ├── main.py
│       └── requirements.txt
│
├── langgraph.json              # LangGraph Platform config
├── Makefile                    # Development commands
└── .env.example                # Environment variables template
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- pnpm

### Environment Setup

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Fill in your API keys in `.env`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...      # For Claude LLM
EXA_API_KEY=...                    # For web search

# Optional (for LangSmith tracing)
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=talent-promo
LANGCHAIN_TRACING_V2=true

# Optional (for production checkpointing)
DATABASE_URL=postgresql://...      # For Postgres checkpointer
REDIS_URL=redis://...              # For Redis checkpointer
```

### Quick Start with Make

```bash
# Install all dependencies
make install

# Start both frontend and backend
make dev-all

# Or start them separately in two terminals:
make dev-backend   # Terminal 1: http://localhost:8000
make dev-frontend  # Terminal 2: http://localhost:3000
```

### Manual Setup

#### Backend (Python)

```bash
cd apps/api

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn main:app --reload --port 8000
```

#### Frontend (Node.js)

```bash
cd apps/web

# Install dependencies
pnpm install

# Run the development server
pnpm dev
```

### LangGraph Development

```bash
# Start LangGraph development server (with Studio UI)
make langgraph-dev

# Deploy to LangGraph Cloud
make langgraph-up
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/optimize/start` | Start a new workflow |
| GET | `/api/optimize/status/{thread_id}` | Get workflow status |
| POST | `/api/optimize/{thread_id}/answer` | Submit Q&A answer |
| GET | `/api/optimize/{thread_id}/stream` | SSE event stream |
| GET | `/api/optimize/{thread_id}/stream/live` | Live astream_events |
| POST | `/api/optimize/{thread_id}/editor/assist` | AI editor assistance |
| POST | `/api/optimize/{thread_id}/editor/regenerate` | Regenerate section |
| POST | `/api/optimize/{thread_id}/export` | Export resume |
| GET | `/api/optimize/{thread_id}/data` | Get full workflow data |

## Key Features

### Memory Hierarchy
- **Full State**: Complete data for persistence and recovery
- **Working Context**: Summarized context for efficient LLM calls
- **Interrupt Payload**: Progressive disclosure for user interactions

### Human-in-the-Loop
Uses LangGraph's `interrupt()` function pattern for:
- Q&A interview questions
- Resume review and approval
- Export confirmation

### Production Checkpointing
Supports multiple backends:
- **Memory**: Development (default)
- **Postgres**: Production persistence
- **Redis**: High-performance caching

### Streaming
- SSE for step updates and interrupt notifications
- `astream_events` for granular LLM token streaming

## Tech Stack

- **Frontend**: Next.js 14, React, TypeScript, Tiptap
- **Backend**: FastAPI, Python 3.11+
- **Orchestration**: LangGraph (replaces Temporal)
- **LLM**: Anthropic Claude
- **Web Search**: EXA API
- **Deployment**: LangGraph Platform (LangSmith)

## Make Commands

```bash
make help            # Show all available commands

# Development
make dev-all         # Start both services in background
make dev-backend     # Start backend only
make dev-frontend    # Start frontend only
make stop            # Stop all services

# Build & Quality
make build           # Build both services
make lint            # Run linters
make test            # Run tests
make clean           # Clean build artifacts

# LangGraph
make langgraph-dev   # Start LangGraph dev server
make langgraph-up    # Deploy to LangGraph Cloud
```

## License

Private - All rights reserved
