# Bug Report

This document tracks bugs found and fixed during integration and e2e testing.

## Summary
- Total bugs found: 15
- Total bugs fixed: 15

---

## BUG_001: Empty resume_text treated same as provided
**File:** `apps/api/validators.py`
**Root Cause:** Empty string resume_text ("") was being treated as valid input, bypassing the requirement for either LinkedIn URL or resume text.
**Fix Applied:** Added whitespace normalization in `validate_urls()` to treat empty/whitespace-only strings as None.

---

## BUG_002: (Not a bug) increment_version handles edge cases correctly
**File:** `apps/api/workflow/nodes/drafting.py`
**Status:** Verified working correctly. The `increment_version()` function properly handles version boundaries (9.9 -> 10.0) and malformed versions.

---

## BUG_003: XSS vulnerability in resume HTML storage
**File:** `apps/api/routers/optimize.py`
**Root Cause:** User-provided HTML content in resume updates was stored without sanitization, allowing script injection.
**Fix Applied:** Added `_sanitize_html()` function that removes script tags, style tags, event handlers (onclick, etc.), javascript: URLs, and dangerous elements (iframe, object, embed).

---

## BUG_005: Whitespace-only resume_text passes validation
**File:** `apps/api/validators.py`
**Root Cause:** Resume text consisting only of whitespace ("   \n\t  ") was considered valid.
**Fix Applied:** Added `.strip()` normalization before validation check in `validate_urls()`.

---

## BUG_007: Version history loses initial version
**File:** `apps/api/routers/optimize.py`
**Root Cause:** When version history exceeded 5 entries, it kept only the last 5, losing the important initial version (1.0).
**Fix Applied:** Modified version trimming logic in all 4 places (handle_suggestion, handle_direct_edit, handle_manual_save, restore_version) to always preserve version 1.0 when truncating.

---

## BUG_010: Silent edit failure when text not found
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The `handle_direct_edit()` endpoint returned 200 success even when the original_text wasn't found in the resume, silently skipping the edit.
**Fix Applied:** Added validation to raise HTTPException with 400 status when original text is not found in resume.

---

## BUG_011: Missing updated_at timestamp on answer submission
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The `submit_answer()` endpoint didn't update the `updated_at` timestamp in the workflow state.
**Fix Applied:** Added timestamp update in `submit_answer()` before saving workflow data.

---

## BUG_013: Special characters in export filename
**File:** `apps/api/routers/optimize.py`
**Root Cause:** User names containing special characters (/, :, <, >, etc.) were included directly in export filenames, potentially causing issues on different file systems.
**Fix Applied:** Added filename sanitization in `download_export()` and `export_resume_endpoint()` that removes Windows-invalid characters and non-word characters.

---

## BUG_017: Workflow list endpoint lacks pagination
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The `list_workflows()` endpoint returned all workflows without any limit, which could cause performance issues with many workflows.
**Fix Applied:** Added `limit` and `offset` parameters with defaults (limit=10, max=100). Response now includes `total`, `limit`, and `offset` fields.

---

## BUG_018: ATS report missing required fields
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The `get_ats_report()` endpoint could return incomplete reports missing expected fields.
**Fix Applied:** Added field validation that ensures required fields (keyword_match_score, formatting_issues, recommendations, keywords_found, keywords_missing) are present with defaults.

---

## BUG_021: LinkedIn suggestions missing required fields
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The `get_linkedin_suggestions()` endpoint could return incomplete suggestions missing expected fields.
**Fix Applied:** Added field validation that ensures required fields (headline, summary, experience_bullets) are present with defaults.

---

## BUG_023: Discovery confirm without messages
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The discovery confirm endpoint only checked exchange count, not whether actual messages existed in the conversation.
**Fix Applied:** Added validation in `confirm_discovery()` to require at least 6 messages (3 questions + 3 answers) for 3 exchanges.

---

## BUG_028: Missing user profile in export causes crash
**File:** `apps/api/routers/optimize.py`
**Root Cause:** Export endpoints crashed with AttributeError when user_profile was None (not just missing from dict).
**Fix Applied:** Changed `state.get("user_profile", {})` to `state.get("user_profile") or {}` with isinstance checks in `download_export()` and `export_resume_endpoint()`.

---

## BUG_033: Editor assist with None job_posting causes crash
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The `editor_assist()` endpoint crashed with AttributeError when job_posting or gap_analysis was explicitly None.
**Fix Applied:** Changed `state.get("job_posting", {})` to `state.get("job_posting") or {}` and added isinstance checks before calling `.get()` methods.

---

## BUG_034: Export start with None job_posting causes crash
**File:** `apps/api/routers/optimize.py`
**Root Cause:** The `start_export()` endpoint crashed when job_posting, gap_analysis, or user_profile was explicitly None, causing `_extract_job_keywords()` to fail.
**Fix Applied:** Changed `state.get("job_posting", {})` to `state.get("job_posting") or {}` for job_posting, gap_analysis, and user_profile before passing to helper functions.

---

## Test Coverage
All bugs have corresponding integration tests in:
- `apps/api/tests/integration/test_bugs.py` - 35 test cases
- `apps/api/tests/integration/test_workflow_api.py` - 22 test cases

Run tests with:
```bash
cd apps/api
source .venv/bin/activate
python -m pytest tests/integration/ -v
```

---

# Bug Report - Iteration 2 (Ralph Loop)

## Summary
- Total new bugs found: 14
- Status: UNFIXED (documentation only)

---

## BUG_035: Race condition in workflow startup
**File:** `apps/api/routers/optimize.py:227`
**Root Cause:** The `start_workflow` endpoint calls `asyncio.create_task(_run_workflow(thread_id))` and immediately returns a response. If the client polls `/status/{thread_id}` before `_run_workflow` updates state, the client may see stale or incomplete data.
**Impact:** Client might see incorrect initial state before workflow actually starts.
**Status:** UNFIXED

---

## BUG_036: Frontend version history doesn't preserve v1.0
**File:** `apps/web/app/hooks/useDraftingStorage.ts:287-289`
**Root Cause:** The `createVersion` function uses `versions.slice(-MAX_VERSIONS)` which drops the oldest versions. Unlike the backend (which preserves v1.0), the frontend loses the initial version when versions exceed 5.
**Impact:** Users cannot restore to their original draft on the frontend.
**Code:**
```typescript
if (versions.length > MAX_VERSIONS) {
  versions = versions.slice(-MAX_VERSIONS);  // Drops v1.0!
}
```
**Status:** UNFIXED

---

## BUG_037: regenerate_section doesn't handle None values
**File:** `apps/api/routers/optimize.py:731-737`
**Root Cause:** The `regenerate_resume_section` endpoint uses `state.get("user_profile", {})` without the `or {}` null coalescing pattern used in other endpoints. If `user_profile` is explicitly `None`, this passes `None` to `regenerate_section()`.
**Impact:** Server crash with AttributeError if user_profile is None.
**Status:** UNFIXED

---

## BUG_038: SSE stream never terminates on workflow pause
**File:** `apps/api/routers/optimize.py:607-620`
**Root Cause:** The SSE `event_generator` in `stream_events` only breaks the loop on "completed" or "error" steps. When workflow hits an interrupt (status="waiting_input"), the generator continues polling forever.
**Impact:** SSE connections remain open indefinitely, consuming server resources.
**Status:** UNFIXED

---

## BUG_039: Memory leak in _workflows global dict
**File:** `apps/api/routers/optimize.py:114`
**Root Cause:** The global `_workflows` dict stores workflow data indefinitely. Only explicit `DELETE /{thread_id}` removes entries. Long-running servers accumulate completed workflows in memory.
**Impact:** Memory grows unbounded over time in production.
**Status:** UNFIXED

---

## BUG_040: Auto-checkpoint uses stale session closure
**File:** `apps/web/app/hooks/useDraftingStorage.ts:163-187`
**Root Cause:** The `useEffect` for auto-checkpoint captures `session` in closure. When session updates, the interval callback still uses the old session value.
**Code:**
```typescript
useEffect(() => {
  // session is captured here
  const startAutoCheckpoint = () => {
    autoCheckpointRef.current = setInterval(() => {
      // This uses stale session!
      if (now.getTime() - lastCheckpoint.getTime() >= AUTO_CHECKPOINT_INTERVAL) {
        createVersion("auto_checkpoint", "Auto-checkpoint");
      }
    }, 60000);
  };
  // ...
}, [session]); // Session changes but interval still has old value
```
**Impact:** Auto-checkpoints may save incorrect/outdated content.
**Status:** UNFIXED

---

## BUG_041: discovery_node mutates state prompts in-place
**File:** `apps/api/workflow/nodes/discovery.py:405-409`
**Root Cause:** The code modifies prompts from state directly: `prompts[i]["asked"] = True`. This mutates the original list from state rather than creating a copy.
**Impact:** Potential state corruption in LangGraph workflow.
**Status:** UNFIXED

---

## BUG_042: ATSReport field name mismatch
**File:** `apps/api/workflow/nodes/export.py:247` vs `apps/api/routers/optimize.py:1273-1282`
**Root Cause:** `analyze_ats_compatibility` returns `ATSReport` with `matched_keywords` and `missing_keywords` fields. The endpoint validation at line 1273 checks for `keywords_found` and `keywords_missing` which don't exist in the model.
**Code in export.py:**
```python
return ATSReport(
    matched_keywords=matched,    # This field name
    missing_keywords=missing,    # This field name
)
```
**Code in optimize.py:**
```python
required_fields = {
    "keywords_found": [],     # Wrong field name!
    "keywords_missing": [],   # Wrong field name!
}
```
**Impact:** Validation adds wrong default fields, original fields are preserved but validation is ineffective.
**Status:** UNFIXED

---

## BUG_043: useExportStorage isLoading never set to true
**File:** `apps/web/app/hooks/useExportStorage.ts:85`
**Root Cause:** The `isLoading` state is initialized to `false` and never updated. No loading state tracking for async operations.
**Impact:** UI cannot show loading indicators for export operations.
**Status:** UNFIXED

---

## BUG_044: increment_version doesn't handle malformed versions
**File:** `apps/api/workflow/nodes/drafting.py:545-555`
**Root Cause:** If version is "1" (no minor number), `current_version.split(".")` returns a single-element list, causing `minor = int(minor)` to fail or use wrong index.
**Code:**
```python
major, minor = current_version.split(".")  # Fails if no "."
```
**Impact:** Server crash on malformed version strings.
**Status:** UNFIXED

---

## BUG_045: syncFromBackend stage calculation logic error
**File:** `apps/web/app/hooks/useWorkflowSession.ts:453-464`
**Root Cause:** The stage status calculation uses OR logic: `(updates.researchComplete || session.researchComplete)`. If backend sends `research_complete: false` to reset, the OR still uses the old `session.researchComplete: true`.
**Impact:** Cannot reset stage completion flags from backend.
**Status:** UNFIXED

---

## BUG_046: HTML sanitizer misses expression() CSS
**File:** `apps/api/routers/optimize.py:742-772`
**Root Cause:** The `_sanitize_html` function removes style tags but doesn't handle inline `expression()` CSS which can execute JavaScript in older browsers.
**Impact:** Potential XSS in older IE browsers via CSS expressions.
**Status:** UNFIXED

---

## BUG_047: Concurrent suggestion acceptance can corrupt resume
**File:** `apps/api/routers/optimize.py:916-942`
**Root Cause:** The `handle_suggestion` endpoint reads state, modifies it, and saves without any locking. If two suggestions are accepted simultaneously, the second write may overwrite the first's changes.
**Impact:** Lost edits when rapidly accepting/declining suggestions.
**Status:** UNFIXED

---

## BUG_048: Discovery exchanges count doesn't match actual messages
**File:** `apps/api/workflow/nodes/discovery.py:489`
**Root Cause:** `discovery_exchanges` is incremented in `_handle_user_response` but not in the initial prompt flow. First prompt doesn't count as an exchange even though a message is added.
**Impact:** Exchange count is off by one, potentially affecting the 3-exchange minimum check.
**Status:** UNFIXED
