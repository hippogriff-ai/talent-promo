# Talent Promo

AI-powered resume optimization platform that helps talent present themselves effectively for target job opportunities.

## Privacy by Design

Resumes contain personal addresses, phone numbers, and other sensitive contact information. To protect user privacy, **we do not store any data on the server**. All workflow state is kept in-memory (MemorySaver) and discarded when the session ends. User preferences and edits persist only in the browser's localStorage.

LangSmith tracing is enabled for quality and debugging purposes. If you are entering real personal information, be aware that traced data may be retained by the tracing provider.

AI safety guardrails are built in to detect and prevent prompt injection, block toxic content, flag biased language, identify sensitive PII (SSN, credit cards), validate that resume claims are grounded in your actual profile, and sanitize LLM output before display.

## Overview

Talent Promo uses an agentic workflow to analyze your profile and a target job posting, then guides you through an intelligent discovery interview to create an ATS-optimized resume tailored specifically for that role.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────┐ │
│  │   Input    │→ │  Research  │→ │  Discovery │→ │  Drafting  │→ │ Export │ │
│  │(URL/Paste) │  │ (Insights) │  │   (Chat)   │  │  (Editor)  │  │(PDF/DX)│ │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └────────┘ │
│                                                        │                     │
│                                        ┌───────────────┴───────────────┐     │
│                                        │   ValidationWarnings.tsx      │     │
│                                        │ (Bias / PII / Claims display) │     │
│                                        └───────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │ SSE Stream
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Backend (FastAPI)                                │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                         AI Safety Guardrails                            │  │
│  │  ┌────────────┐ ┌──────────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌────────┐ │  │
│  │  │ Injection  │ │ Content  │ │  Bias  │ │ PII  │ │Claims│ │ Output │ │  │
│  │  │ Detector   │ │Moderator │ │Detector│ │Detect│ │ Valid│ │Sanitize│ │  │
│  │  └────────────┘ └──────────┘ └────────┘ └──────┘ └──────┘ └────────┘ │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                         LangGraph Workflow                              │  │
│  │  [ingest] → [research] → [discovery] → [qa] → [draft] → [editor] → [export] │
│  │                            ↻ interrupt()  ↻              ↻             │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────────────────┐ │
│  │   EXA API       │  │  Anthropic API  │  │  MemorySaver (in-memory)     │ │
│  │   (Web Search)  │  │  (Claude)       │  │  + Audit Logger (JSON)        │ │
│  └─────────────────┘  └─────────────────┘  └───────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Guardrails

| Layer | Module | Coverage |
|-------|--------|----------|
| **Injection Detection** | `injection_detector.py` | 25+ patterns, all user-facing endpoints |
| **Content Moderation** | `content_moderator.py` | Violence, hate speech, illegal content blocking |
| **Bias Detection** | `bias_detector.py` | 40+ terms across age/gender/race/disability |
| **PII Detection** | `pii_detector.py` | SSN, credit cards, bank accounts; allows email/phone |
| **Claim Validation** | `claim_validator.py` | Verifies resume claims against source profile |
| **Output Sanitization** | `output_validators.py` | AI self-references, refusal leak detection |
| **Audit Logging** | `audit_logger.py` | Structured JSON logs for all security events |

See `specs/AI_GUARDRAILS_SPEC.md` for full implementation details.

## Workflow

The LangGraph workflow progresses through 7 nodes:

1. **Ingest** (`ingest.py`): Fetch profile (URL or pasted text) + job posting. Extracts name/company via regex, stores raw text directly (no LLM parsing).
2. **Research** (`research.py`): Company culture, tech stack, similar employees via EXA. Includes gap analysis.
3. **Discovery** (`discovery.py`): Strength-first interview with agenda system. Seniority-adaptive questioning (early/mid/senior). Skippable.
4. **Q&A** (`graph.py`): Human-in-the-loop interrupt for discovery responses (up to 10 rounds).
5. **Draft** (`drafting.py`): ATS-optimized resume generation with 5 principles: Faithful, Concise, Hierarchy-Preserving, Focused, Polished.
6. **Editor Assist** (`drafting.py`): AI-powered editing in Tiptap canvas with suggestion system.
7. **Export** (`export.py`): Export to DOCX or PDF with contact info preservation.

### Drafting Quality System

The drafting node is designed to produce resumes that sound human, not AI-generated. Tuned via 12 iterations of LLM-as-a-judge grading to a stable **88+/100** overall score.

**5 Core Principles** (in priority order):
1. **Faithful**: Every claim traceable to source. No scope merging ("6yr backend + 1yr AI" stays separate). No invented metrics. No employer-scale attribution.
2. **Concise**: Every bullet under 15 words. One idea per bullet. Formula: `Action Verb + What + Metric`.
3. **Hierarchy-Preserving**: Candidate's most prominent experience stays most prominent. No reordering for keywords.
4. **Focused**: Top 3-5 job requirements addressed deeply, not all superficially. Silence beats a weak claim.
5. **Polished**: Zero AI-tell words, zero filler, varied rhythm.

**Programmatic Quality Checks** (`validate_resume()`):
- Bullet word count (>15 words flagged)
- Compound sentence detection (two achievements joined with "and"/"while")
- Summary length enforcement (<50 words)
- AI-tell word/phrase detection (24 words + 13 phrases)
- Quantification rate (warns when <50% of bullets have metrics)
- Rhythm variation (flags 3+ consecutive same-length bullets)
- Scope conflation detection (summary "N years [domain]" cross-referenced against source)
- Scale attribution detection (employer-scale language not in source)
- Keyword coverage (warns when <30% of job keywords appear)
- Reverse chronological ordering check

**LLM-as-a-Judge Grading** (6 dimensions):

| Dimension | Weight | Stable Score |
|-----------|--------|-------------|
| Source Fidelity | 25% | 90+ |
| Job Relevance | 20% | 82+ |
| Conciseness | 15% | 88+ |
| Narrative Hierarchy | 15% | 91+ |
| Narrative Coherence | 15% | 85+ |
| ATS Optimization | 10% | 93+ |
| **Overall** | **100%** | **88.0-88.7** |

## Project Structure

```
talent-promo/
├── apps/
│   ├── web/                          # Next.js frontend (port 3000)
│   │   └── app/
│   │       ├── optimize/             # Resume optimization wizard
│   │       ├── components/optimize/  # Step components, ValidationWarnings
│   │       ├── hooks/                # useWorkflow, useSSEStream, useClientMemory
│   │       └── types/                # TypeScript interfaces (guardrails.ts)
│   │
│   └── api/                          # FastAPI backend (port 8000)
│       ├── workflow/                  # LangGraph workflow
│       │   ├── graph.py              # Workflow definition + routing
│       │   ├── state.py              # ResumeState schema
│       │   └── nodes/                # ingest, research, discovery, drafting, export
│       ├── guardrails/               # AI Safety Guardrails (7 modules)
│       │   ├── __init__.py           # validate_input(), validate_output()
│       │   ├── injection_detector.py # Prompt injection detection
│       │   ├── content_moderator.py  # Toxic content blocking
│       │   ├── bias_detector.py      # Bias term detection
│       │   ├── pii_detector.py       # PII detection/redaction
│       │   ├── claim_validator.py    # Resume claim grounding
│       │   ├── output_validators.py  # LLM output sanitization
│       │   └── audit_logger.py       # Security event logging
│       ├── evals/                    # Prompt tuning infrastructure
│       │   ├── graders/              # LLM-as-a-judge graders
│       │   ├── datasets/             # Silver datasets (discovery, drafting, memory)
│       │   ├── run_drafting_tuning.py  # CLI: python -m evals.run_drafting_tuning
│       │   └── run_discovery_tuning.py # CLI: python -m evals.run_discovery_tuning
│       ├── routers/
│       │   └── optimize.py           # API endpoints (guardrails-protected)
│       └── tests/                    # 673+ unit tests
│
├── specs/                            # Feature specs
│   ├── AI_GUARDRAILS_SPEC.md
│   └── DRAFTING_QUALITY_SPEC.md
├── CONTINUITY.md                     # Session continuity ledger
└── Makefile                          # Development commands
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

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/optimize/start` | Start a new workflow |
| GET | `/api/optimize/status/{thread_id}` | Get workflow status |
| POST | `/api/optimize/{thread_id}/answer` | Submit discovery answer |
| GET | `/api/optimize/{thread_id}/stream` | SSE event stream |
| POST | `/api/optimize/{thread_id}/editor/assist` | AI editor assistance |
| POST | `/api/optimize/{thread_id}/editor/regenerate` | Regenerate section |
| POST | `/api/optimize/{thread_id}/drafting/save` | Save draft edits |
| POST | `/api/optimize/{thread_id}/drafting/approve` | Approve draft |
| POST | `/api/optimize/{thread_id}/drafting/revert` | Go back to editing |
| GET | `/api/optimize/{thread_id}/export/download/{format}` | Download PDF/DOCX |

## Prompt Tuning

The evals infrastructure supports iterative prompt improvement using LLM-as-a-judge grading with memory-guided tuning loops.

### Drafting Tuning (6 dimensions)

```bash
cd apps/api

# Run programmatic validation only (no API cost)
python -m evals.run_drafting_tuning --validate

# Run one grading iteration
python -m evals.run_drafting_tuning --iterate

# See accumulated learnings
python -m evals.run_drafting_tuning --show-memory

# Reset for fresh baseline
python -m evals.run_drafting_tuning --reset --reset-memory
```

Grading dimensions: source_fidelity (25%), job_relevance (20%), conciseness (15%), narrative_hierarchy (15%), narrative_coherence (15%), ats_optimization (10%).

**Tuning Results**: 13 iterations, baseline 86.4 → stable 88.0-88.7. Key learning: any mandatory generation requirement not in source material causes fabrication. Quantification and authenticity markers must be subordinate to faithfulness.

### Discovery Tuning (5 dimensions)

```bash
cd apps/api
python -m evals.run_discovery_tuning --iterate
```

## Key Features

### Human-in-the-Loop
Uses LangGraph's `interrupt()` function for:
- Discovery interview questions (skippable)
- Resume review and approval
- Go back to edit from export/completion

### Streaming
- SSE for step updates and interrupt notifications
- `astream_events` for granular LLM token streaming

### Client Memory
Browser-side memory system (localStorage):
- Session history (last 20 sessions)
- Experience library (accumulated across sessions)
- Learned edit preferences with confidence scores
- Profile/job edits per thread

## Tech Stack

- **Frontend**: Next.js 14, React, TypeScript, Tiptap (rich text editor)
- **Backend**: FastAPI, Python 3.11+
- **Orchestration**: LangGraph with MemorySaver (in-memory, no persistence)
- **LLM**: Anthropic Claude
- **Web Search**: EXA API
- **Safety**: Custom guardrails (7 modules, 182+ tests)

## License

Private - All rights reserved
