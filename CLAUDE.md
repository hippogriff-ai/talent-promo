# Talent Promo - Project Instructions

## Architecture Overview
- **Backend**: FastAPI (port 8000) at `apps/api/`
- **Frontend**: Next.js (port 3001) at `apps/web/`
- **Workflow Engine**: LangGraph with checkpointing
- **LLM Provider**: Anthropic (Claude)

## Specs
Stage specs are in `specs/` directory. Read the relevant spec before executing.

## Continuity
Read `CONTINUITY.md` before executing.
After finish, document your changes on a high level in `CONTINUITY.md`

### Compaction Rule
When `CONTINUITY.md` exceeds 1000 lines, compact the oldest 75% of content: replace detailed entries with a brief summary (bullet points, key facts only), preserving the most recent 25% verbatim. Keep the header sections (Goal, Constraints, Key decisions) intact.

## Stage Transition Rules

The optimization workflow progresses through these stages:

```
RESEARCH → DISCOVERY → DRAFTING → EXPORT → COMPLETE
```

### RESEARCH → DISCOVERY
- **Auto-advance**: Yes
- **Description**: Automatically transitions once research phase completes

### DISCOVERY → DRAFTING
- **Requires**: `state.discovery_confirmed === true`
- **Auto-advance**: No (wait for user confirmation)
- **Description**: User must confirm discovery findings before drafting begins

### DRAFTING → EXPORT
- **Requires**: `state.draft_approved === true`
- **Auto-advance**: No (wait for user confirmation)
- **Description**: User must approve draft before export

### EXPORT → COMPLETE
- **Auto-advance**: Yes
- **Final action**: Display success screen with download links

## Key Files
- `apps/api/workflow/graph.py` - LangGraph workflow definition
- `apps/api/routers/optimize.py` - Optimization API endpoints
- `apps/api/main.py` - FastAPI application entry

## Persistence
All state persists to browser localStorage with prefix `resume_agent:`

## Validation
- Python tests: `python -m pytest tests/validate_{stage}.py -v`


```
