# Continuity Ledger

## Goal
Execute 5-stage resume agent build workflow (specs/ralph_orchestrator.md)
- Success criteria: All 5 stages pass tests, output <promise>ALL_STAGES_BUILT</promise>

## Constraints/Assumptions
- Backend: FastAPI on port 8000
- Frontend: Next.js on port 3001
- Main workflow uses Anthropic (Claude), not OpenAI
- LangGraph checkpointing for graph state persistence
- **SQLite doesn't work with async nodes** - requires Postgres for production persistence
- Each stage must pass tests before proceeding to next

## Key decisions
- **LangGraph over Temporal**: LangGraph's checkpointing is simpler for this use case
- **MemorySaver for dev, PostgresSaver for prod**: SqliteSaver is sync-only
- LangSmith tracing: env vars must be set BEFORE LangChain imports

## State
- Done:
  - Workflow persistence infrastructure (checkpointer factory, recovery logic)
  - **Stage 1 Research (specs/step1_research.md)**:
    - Backend tests: 16/16 passing (`apps/api/tests/test_research_workflow.py`)
    - URL validation (LinkedIn + Job URLs)
    - EXA fetch with 3-retry logic + exponential backoff
    - Profile + Job parsing via LLM
    - Company research synthesis (culture, tech stack, similar hires, news)
    - Hiring criteria extraction + ideal profile generation
    - Frontend: useResearchStorage hook (localStorage persistence)
    - Frontend: ResearchProgress component (7 sub-task tracking)
    - Frontend: SessionRecoveryPrompt component (resume/start-fresh UI)
    - Frontend build passes
  - **Stage 2 Discovery (specs/step2_discovery.md)**:
    - Backend tests: 27/27 passing (`apps/api/tests/test_discovery.py`)
    - State models: GapItem, OpportunityItem, DiscoveryPrompt, DiscoveredExperience, DiscoveryMessage
    - Discovery node: generate prompts, process responses, extract experiences
    - Gap analysis with linked job requirements
    - Discovery prompts ordered by priority/relevance
    - LangGraph interrupt() for human-in-the-loop conversation
    - Discovery confirm endpoint (requires 3+ exchanges)
    - Frontend tests: 48/48 passing
    - Frontend: useDiscoveryStorage hook (localStorage persistence)
    - Frontend: GapAnalysisDisplay component (gaps/strengths/opportunities)
    - Frontend: DiscoveryChat component (conversation UI with progress)
    - Frontend: DiscoveredExperiences component (extracted experiences list)
    - Frontend: DiscoveryStep component (main container with session recovery)
    - Frontend build passes
  - **Stage 3 Drafting (specs/step3_drafting.md)**:
    - Backend tests: 26/26 passing (`apps/api/tests/test_drafting.py`)
    - State models: DraftingSuggestion, DraftVersion, DraftChangeLogEntry, DraftValidationResult
    - Drafting node: generates resume HTML + improvement suggestions
    - Resume validation (summary length, experience count, action verbs, skills/education sections)
    - API endpoints: drafting/state, drafting/suggestion (accept/decline), drafting/edit, drafting/save, drafting/restore, drafting/versions, drafting/approve
    - Version control: max 5 versions, increment version on each action
    - Frontend tests: 29/29 passing
    - Frontend: useDraftingStorage hook (localStorage persistence + version control)
    - Frontend: useSuggestions hook (API calls for accept/decline)
    - Frontend: SuggestionCard component (accept/decline UI)
    - Frontend: VersionHistory component (restore previous versions)
    - Frontend: DraftingStep component (Tiptap editor + suggestion panel)
    - Frontend build passes
  - **Stage 4 Export (specs/step4_export.md)**:
    - Backend tests: 34/34 passing (`apps/api/tests/test_export.py`)
    - State models: ATSReport, LinkedInSuggestion, ExportOutput, ExportStep
    - Export node: ATS optimization, keyword analysis, LinkedIn suggestions
    - File generation: PDF (WeasyPrint), DOCX (python-docx), TXT, JSON
    - ATS analysis: keyword matching, formatting issues, recommendations
    - LinkedIn suggestions: headline (220 char), summary, experience bullets
    - API endpoints: export/start, export/state, export/ats-report, export/linkedin, export/download/{format}, export/copy-text, export/re-export
    - Frontend tests: 89/89 passing (12 new export hook tests)
    - Frontend: useExportStorage hook (localStorage persistence)
    - Frontend: ATSReportDisplay component (score visualization, keywords)
    - Frontend: LinkedInSuggestionsDisplay component (copy-to-clipboard)
    - Frontend: ExportStep component (progress tracking, downloads, session recovery)
    - Frontend build passes
  - **Stage 5 (specs/step5_orchestation.md)**:
    - Frontend tests: 158/158 passing (19 new orchestration tests)
    - useWorkflowSession hook: unified session management across 4 stages
    - WorkflowStepper component: 4-stage stepper (Research → Discovery → Drafting → Export)
    - SessionRecoveryModal component: resume/start-fresh on return
    - StartNewSessionDialog component: confirmation before clearing session
    - ErrorRecovery component: retry/start-fresh with preserved progress
    - CompletionScreen component: success screen with download links
    - Stage guards: prevent access to future stages, redirect to earliest incomplete
    - Stage transitions: automatic unlock on completion, confirmation required for manual transitions
    - Error recovery: save state before error, retry from last state, preserve completed stages
    - Backend tests: 160/160 passing
    - Frontend build passes
  - **Bug Fixes (integration testing)**:
    - Integration tests: 57/57 passing (`apps/api/tests/integration/`)
    - Backend tests: 174/174 passing
    - BUG_003: XSS vulnerability fixed - HTML sanitization added
    - BUG_005: Whitespace-only resume_text validation fixed
    - BUG_007: Version history now preserves initial version (1.0)
    - BUG_010: Silent edit failure now returns 400 error
    - BUG_011: Answer submission now updates timestamp
    - BUG_013: Special characters in export filename sanitized
    - BUG_017: Workflow list now supports pagination (limit/offset)
    - BUG_018: ATS report validates required fields
    - BUG_021: LinkedIn suggestions validates required fields
    - BUG_023: Discovery confirm requires message history
    - BUG_028: Export handles None user_profile gracefully
    - BUG_033: Editor assist handles None job_posting/gap_analysis
    - BUG_034: Export start handles None job_posting/gap_analysis/user_profile
    - See `bugs/bug_report.md` for full details (15 bugs documented)
  - **Code Simplification (2025-01-10)**:
    - Backend: 174 tests passing, Frontend: 158 tests passing
    - Extracted `_add_version_and_prune()` helper in optimize.py (consolidated 4 duplicate version management blocks)
    - Extracted `_sanitize_filename()` and `_get_export_filename_base()` helpers in optimize.py
    - Consolidated routing functions in graph.py with `_route_or_error()` helper
    - Removed unused `common_job_domains` variable in validators.py
    - Extracted `_extract_json_from_response()` in discovery.py (consolidated 2 duplicate JSON parsing blocks)
    - Extracted `_extract_content_from_code_block()` in drafting.py (consolidated 2 duplicate code block parsing)
    - Added `getCompletionFlagForStage()` helper in useWorkflowSession.ts
    - Extracted `saveSessionToStorage()` and `getSessionsFromStorage()` helpers in useDraftingStorage.ts (consolidated 10+ duplicate localStorage patterns)
  - **Bug Hunt - Ralph Loop (2025-01-10)**:
    - Found 14 new bugs (BUG_035-BUG_048) across backend and frontend
    - Key findings:
      - BUG_035: Race condition in workflow startup (asyncio.create_task returns before state saved)
      - BUG_036: Frontend version history drops v1.0 (unlike backend)
      - BUG_038: SSE stream never terminates on workflow pause
      - BUG_039: Memory leak in _workflows global dict
      - BUG_042: ATSReport field name mismatch (matched_keywords vs keywords_found)
      - BUG_047: Concurrent suggestion acceptance can corrupt resume (no locking)
    - See `bugs/bug_report.md` for full details
  - **Frontend Redesign (2025-01-10)**:
    - Landing page (`apps/web/app/page.tsx`): Full redesign with hero section, integrated input form, features, benefits
    - Header component (`apps/web/app/components/layout/Header.tsx`): Responsive navigation with logo, links, mobile menu
    - Onboarding guide (`apps/web/app/components/layout/OnboardingGuide.tsx`): 4-step walkthrough modal for first-time users
    - Optimize page (`apps/web/app/optimize/page.tsx`): Auto-starts workflow from pending input, shows "No Active Workflow" when accessed directly
    - Flow: Landing page form → localStorage → /optimize auto-start → workflow stepper
    - CSS animations: Blob animation for hero background (`apps/web/app/globals.css`)
- Now: UX improvements complete
  - **Paste Job Description Feature (2025-01-10)**:
    - Added fallback for when job URL scraping fails (JS-rendered pages like Lever)
    - Backend: Added `uploaded_job_text` field to workflow state
    - Backend: Updated `create_initial_state` in graph.py to accept `uploaded_job_text`
    - Backend: Updated `parallel_ingest_node` to check for pasted job text before fetching URL
    - Backend: Updated validators.py to accept job_text as alternative to job_url
    - Backend: Updated API `/start` endpoint to accept `job_text` parameter
    - Frontend: Added job input mode toggle (URL vs Paste) on landing page form
    - Frontend: Updated useWorkflow hook to pass jobText to API
    - Frontend: Updated optimize page to handle jobText in input data
    - Improved error messages to suggest pasting job description when URL fetch fails
- Next: Fix the newly documented bugs (BUG_035-BUG_048)
  - **Performance Optimization (2025-01-10)**:
    - Reduced workflow time from ~200s to ~60s (3x faster)
    - **Ingest node**: Parallel LLM parsing (profile + job parsed simultaneously)
    - **Research node**: All 4 EXA searches run in parallel via asyncio.gather()
    - **Analysis merged into Research**: Single LLM call does both research synthesis + gap analysis
    - **Graph simplified**: Removed analyze node, research routes directly to discovery
    - Files modified:
      - `apps/api/workflow/nodes/ingest.py` - parallel LLM parsing
      - `apps/api/workflow/nodes/research.py` - parallel EXA + merged analysis
      - `apps/api/workflow/graph.py` - removed analyze node from flow
  - **Progress Visibility & Research Review (2025-01-10)**:
    - **Real-time progress messages**: Created side-channel progress store (`workflow/progress.py`) that updates DURING node execution, not just after completion
    - **Frontend receives progress immediately**: Status endpoint merges real-time progress with LangGraph state
    - **Research Review Screen**: Added transition screen after research completes, before Discovery
      - Shows full profile, job, gap analysis, research insights
      - User must click "Continue to Discovery" to proceed
      - Prevents auto-advancing without reviewing retrieved data
    - Files modified:
      - `apps/api/workflow/progress.py` - new real-time progress store with contextvars
      - `apps/api/routers/optimize.py` - imports progress functions, sets context during workflow execution
      - `apps/api/workflow/nodes/ingest.py` - emits real-time progress during URL fetching and LLM parsing
      - `apps/api/workflow/nodes/research.py` - emits real-time progress during EXA searches and analysis
      - `apps/web/app/optimize/page.tsx` - added research review screen with Continue button
      - `apps/web/app/hooks/useWorkflow.ts` - fixed missing progressMessages in refreshStatus
      - `apps/web/app/components/optimize/ResearchStep.tsx` - Live Progress feed UI
  - **UI Polish (2025-01-10)**:
    - **Live Progress limited to 3 items**: Changed from 8 to 3 rolling updates for cleaner UI
    - **Show More modals with form editor**: Added to Profile and Job cards in Research Complete view
      - User-friendly tiered form instead of raw JSON (non-tech users)
      - Profile form: Basic info, Experience (add/remove roles), Skills, Education
      - Job form: Job details, Requirements, Preferred qualifications, Tech stack, Responsibilities, Benefits
      - Allows manual correction of parsing errors without needing to understand JSON
    - Files modified:
      - `apps/web/app/components/optimize/ResearchStep.tsx` - Limited progressMessages to 3
      - `apps/web/app/optimize/page.tsx` - Added Show More buttons and form-based edit modals
- Now: UI polish complete and tested
  - Verified Live Progress shows only 3 rolling updates
  - Verified Profile form editor works (Basic Info, Experience, Skills, Education sections)
  - Verified Job form editor works (Job Details, Requirements, Preferred Qualifications, Tech Stack, Responsibilities, Benefits)
- Next: Fix the newly documented bugs (BUG_035-BUG_048)

## Open questions
- None currently

## Working set
- specs/step1_research.md → specs/step5_orchestration.md (build specs)
- apps/api/workflow/graph.py (workflow definition)
- apps/api/routers/optimize.py (API endpoints)
- apps/web/ (Next.js frontend)

## Production Persistence Setup
To enable persistence that survives restarts:
1. Set up PostgreSQL database
2. Update .env:
   ```
   LANGGRAPH_CHECKPOINTER=postgres
   DATABASE_URL=postgresql://user:pass@localhost:5432/talent_promo
   ```
3. Install: `pip install langgraph-checkpoint-postgres`
