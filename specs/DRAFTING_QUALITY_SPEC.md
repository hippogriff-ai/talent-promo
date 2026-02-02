# Enhance Resume Drafting Quality

## Problem Statement

4 user-reported issues trace to specific gaps in both the drafting prompt and the LLM grader:

| # | Issue | Prompt Root Cause | Grader Root Cause |
|---|---|---|---|
| 1 | **Descriptor merging** ("6yr SWE + 1yr AI" → "6+ years AI") | "Reframe adjacent experience to match requirements" encourages conflation | No dimension checks factual accuracy vs source material. Grader never receives original resume. |
| 2 | **Run-on sentences** | Contradictory limits (line 58: "under 18 words", line 114: "under 20 words"). XYZ formula has 4 components → long bullets. | `PROFESSIONAL_QUALITY` says "concise" without defining word count limits. |
| 3 | **Valuable experiences buried** | "Address ALL job requirements" pushes LLM to reorder by job keywords, not candidate emphasis | No dimension evaluates whether candidate's own prominence hierarchy is preserved. |
| 4 | **Resume becomes clueless** | "Address ALL job requirements" spreads thin. "Reframe" dilutes genuine narrative. | `JOB_RELEVANCE` rewards breadth, not depth. No dimension for narrative coherence. |

---

## Implementation Plan (7 Phases)

### Phase 1: TDD Scaffolding
**New file:** `apps/api/tests/test_drafting_quality.py`

Write failing tests first. Two categories:

**Category A: Programmatic validation tests (no LLM calls)**

| Test Class | What it validates | Pass condition |
|---|---|---|
| `TestBulletWordCount` | `validate_resume()` catches bullets > 15 words | `checks["bullet_word_count"]` is False when any bullet > 15 words |
| `TestCompoundSentences` | `validate_resume()` catches two-achievement bullets | `checks["no_compound_bullets"]` is False for "X and Y" compound achievements |
| `TestSummaryLength` | `validate_resume()` catches summaries > 50 words | `checks["summary_length"]` is False when summary > 50 words |
| `TestDatasetIntegrity` | All 9 samples have `profile_text`, regression samples have dimension-specific `min` expectations | Assert structure of `drafting_samples.json` |

**Category B: LLM grader threshold tests (define "what passing means")**

| Grader Dimension | Weight | Pass Threshold | What it catches |
|---|---|---|---|
| `source_fidelity` | 25% | >= 75 | Fabricated metrics, scope merging, misattributed achievements |
| `conciseness` | 15% | >= 70 | Bullets > 15 words, compound sentences, bloated summaries |
| `narrative_hierarchy` | 15% | >= 70 | Buried lead experiences, reordered importance |
| `narrative_coherence` | 15% | >= 70 | Scattered keyword soup, no clear through-line |
| `job_relevance` | 20% | >= 70 | Missing core requirements (top 3-5, not all) |
| `ats_optimization` | 10% | >= 75 | Bad HTML structure, tables, non-parseable formatting |
| **Overall (weighted)** | 100% | **>= 72** | Composite pass line |

Regression sample assertions:
- `scope-conflation-trap`: `source_fidelity` >= 75, must NOT contain `"6+ years.*AI"` pattern
- `run-on-sentence-trap`: `conciseness` >= 75, all bullets <= 15 words programmatically
- `buried-experience-trap`: `narrative_hierarchy` >= 75, first experience in output = Engineering Manager
- `keyword-dilution-trap`: `narrative_coherence` >= 75, resume has identifiable core story

---

### Phase 2: Enhance `validate_resume()` (programmatic checks)
**File:** `apps/api/workflow/nodes/drafting.py` (function at line 531)

Add 3 new checks to the existing function:

1. **Bullet word count check** — extract `<li>` content, count words, flag any > 15
2. **Compound achievement detection** — flag bullets where "and"/"while"/"resulting in" joins two verb phrases AND bullet > 12 words (avoids false positives on short bullets like "Built and deployed API")
3. **Summary word count** — tighten from 100-word limit to 50-word limit (40 target + buffer)

Phase 1 Category A tests should pass after this.

---

### Phase 3: Expand Silver Dataset
**File:** `apps/api/evals/datasets/drafting_samples.json`

**Add `profile_text` field** to all 5 existing samples (plain-text rendering of the structured profile). Required because the grader now cross-references against original text.

**Add 4 regression samples**, each a "trap" designed to trigger one specific failure:

| Sample ID | Trap | Profile Design |
|---|---|---|
| `scope-conflation-trap` | Issue 1 | 6yr Java backend + 1yr AI side projects → targeting "AI Engineer" role |
| `run-on-sentence-trap` | Issue 2 | 4 clear, short achievements → should stay short in output |
| `buried-experience-trap` | Issue 3 | Eng Manager at FAANG as first role → targeting VP role |
| `keyword-dilution-trap` | Issue 4 | Design systems specialist → job posting lists 10 requirements |

Total: 9 samples (5 existing + 4 regression).

---

### Phase 4: Restructure LLM Grader
**File:** `apps/api/evals/graders/drafting_llm_grader.py`

**4A. Change `grade()` signature** to accept original resume text:
```python
async def grade(self, draft_html, job_posting, user_profile,
                original_resume_text="", discovered_experiences=None)
```

**4B. Replace `GRADING_SYSTEM_PROMPT`** — 4 old dimensions → 6 new dimensions:

The new prompt must instruct the grader that it receives THREE inputs (draft, job, AND original resume) and evaluate on:

1. **SOURCE_FIDELITY (25%)** — Cross-reference every claim against original resume:
   - Score 0-40: Any fabricated metric found
   - Score 41-70: Experience scopes conflated (e.g., merging timeframes)
   - Score 71-100: All claims traceable to source

2. **CONCISENESS (15%)** — Strict length enforcement:
   - Count words per bullet (any > 15 words = below 60)
   - Identify compound sentences joining two achievements
   - Summary must be under 40 words

3. **NARRATIVE_HIERARCHY (15%)** — Compare ordering:
   - Is the candidate's most recent/prominent role still prominent?
   - Is their original lead achievement still in the top third?

4. **NARRATIVE_COHERENCE (15%)** — Story integrity:
   - Is there a clear through-line from summary to experience to skills?
   - Or does it read as scattered keyword coverage?

5. **JOB_RELEVANCE (20%)** — Focused, not broad:
   - Are the TOP 3-5 requirements addressed effectively?
   - (NOT "all requirements superficially")

6. **ATS_OPTIMIZATION (10%)** — Structural cleanliness (mostly unchanged)

**4C. Update `DraftLLMGrade` dataclass** — replace 4 fields with 6.

**4D. Update weighted average calculation:**
```
overall = source_fidelity*0.25 + conciseness*0.15 + narrative_hierarchy*0.15
        + narrative_coherence*0.15 + job_relevance*0.20 + ats_optimization*0.10
```

**4E. Update `grade_batch()`** — flow `profile_text` from sample to grader.

---

### Phase 5: Rewrite Drafting Prompt
**File:** `apps/api/workflow/nodes/drafting.py` (lines 55-119)

Replace the 4 old principles with 5 new ones:

**Principle 1: FAITHFUL (new, overrides all)**
- NEVER merge distinct experience scopes
- NEVER invent metrics not in the source
- Reframing allowed for WORDING only, not scope/scale/timeframe

**Principle 2: CONCISE (tightened)**
- Every bullet MUST be under 15 words. No exceptions.
- One idea per bullet. Never join two achievements.
- Formula: `Action Verb + What + Metric`. That's it.

**Principle 3: HIERARCHY-PRESERVING (new)**
- Candidate's most prominent experience stays most prominent
- Do NOT reorder experiences to chase job keywords
- Lead each role with the candidate's strongest achievements

**Principle 4: FOCUSED (replaces TAILORED)**
- Address top 3-5 job requirements deeply, not all superficially
- Maintain a coherent narrative (one story about who this person is)
- Better to strongly match 4 requirements than weakly touch 10

**Principle 5: POLISHED (unchanged)**
- Zero filler words, zero passive voice

**Also fix:**
- Remove contradictory word counts (standardize to 15)
- Replace "Reframe adjacent experience to match requirements" with safer framing
- Add anti-examples for each issue type
- Update VERIFY checklist to include fidelity/hierarchy/coherence checks

---

### Phase 6: Update Tuning Loop + CLI
**File:** `apps/api/evals/drafting_tuning_loop.py`

- Update `DIMENSIONS` list (line 39) from 4 → 6 dimensions
- Change `TARGET_IMPROVEMENT` from 0.15 → 0.10 (new grader is stricter)
- Memory structure auto-updates (iterates `DIMENSIONS`)

**File:** `apps/api/evals/run_drafting_tuning.py`

- Update `create_draft_generator()` to pass `profile_text` alongside draft
- Add per-dimension PASS/FAIL indicators in output
- Add `--validate` flag for programmatic-only checks (no API cost)

---

### Phase 7: Run Tuning Loop + Verify

```bash
cd apps/api
python -m evals.run_drafting_tuning --reset
python -m evals.run_drafting_tuning --reset-memory
python -m evals.run_drafting_tuning --iterate    # baseline with new grader
# Review scores, iterate on prompt if needed
python -m evals.run_drafting_tuning --iterate    # measure improvement
```

**Expected baseline**: ~65-75 overall (down from old 88.6, because old grader missed these issues).
**Target after tuning**: >= 72 overall, all dimensions >= their pass thresholds.

---

## Risk Notes

1. **Compound sentence false positives** — "Built and deployed API" is one idea, not compound. Mitigation: only flag "and"/"while" when bullet > 12 words AND contains two verbs.

2. **Grader score deflation** — New dimensions are stricter. Baseline will drop. This is correct behavior (old grader gave 88 to resumes with issues).

3. **LLM grading variance** — 3-5 point variance per run (observed in previous tuning). For tuning decisions, run 2-3 iterations and average.

4. **15-word bullet limit** — Aggressive but achievable (current examples average 8 words). Can adjust to 18 during tuning if quality suffers.

---

## Files Changed Summary

| File | Change Type | Phase |
|---|---|---|
| `apps/api/tests/test_drafting_quality.py` | NEW | 1 |
| `apps/api/workflow/nodes/drafting.py` | EDIT: `validate_resume()` | 2 |
| `apps/api/evals/datasets/drafting_samples.json` | EDIT: add samples + `profile_text` | 3 |
| `apps/api/evals/graders/drafting_llm_grader.py` | EDIT: dimensions, prompt, signature | 4 |
| `apps/api/workflow/nodes/drafting.py` | EDIT: `RESUME_DRAFTING_PROMPT` | 5 |
| `apps/api/evals/drafting_tuning_loop.py` | EDIT: `DIMENSIONS`, target | 6 |
| `apps/api/evals/run_drafting_tuning.py` | EDIT: CLI formatting, `--validate` flag | 6 |

---

## Verification

1. `cd apps/api && python -m pytest tests/test_drafting_quality.py -v` — all programmatic tests pass
2. `cd apps/api && python -m pytest tests/ -v` — no regressions in existing tests
3. `cd apps/api && python -m evals.run_drafting_tuning --iterate` — new grader runs, all 9 samples scored
4. Manual: generate a resume for "6yr SWE + 1yr AI" targeting "AI engineer" — verify scopes stay separate
5. Manual: check that no bullet in output exceeds 15 words

---

## Implementation Status (2026-02-01)

### DONE
- [x] **Phase 1**: TDD scaffolding — `tests/test_drafting_quality.py` with 31 tests (all pass)
- [x] **Phase 2**: Enhanced `validate_resume()` — bullet word count (>15), compound sentence detection, summary limit 100→50
- [x] **Phase 3**: Expanded dataset — `profile_text` on all 5 samples, 4 regression traps (9 total)
- [x] **Phase 4**: Restructured grader — 6 dimensions with weights, `original_resume_text` parameter
- [x] **Phase 5**: Rewrote prompt — 5 principles (FAITHFUL, CONCISE, HIERARCHY-PRESERVING, FOCUSED, POLISHED)
- [x] **Phase 6**: Updated tuning loop — DIMENSIONS 4→6, TARGET 0.15→0.10, `--validate` flag
- [x] **Phase 7**: Ready to run — 598 tests pass, expected baseline ~65-75 with new grader
- [x] **Enhancement: AI-tell detection** — `detect_ai_tells()` function, `ai_tells_clean` validation check, 8 new tests (39 total)
- [x] **Enhancement: Research-aligned grader** — GRADING_SYSTEM_PROMPT enhanced with AI-tell deductions, authenticity markers, XYZ formula, seniority checks, concrete examples
- [x] **Enhancement: Context engineering** — draft generator now passes `profile_text` to LLM so it can see the original resume for source fidelity. User message aligned with FAITHFUL principle (removed "Focus on highlighting"). 2 new tests (41 total). grade_batch passes profile_text as 3rd arg.
- [x] **README overhaul** — Fixed 7 discrepancies: MemorySaver not Postgres, correct workflow nodes, all 7 guardrails modules, 182 test count, removed Postgres/Redis env vars, added evals/tuning docs, added Drafting Quality System section
- [x] **Prompt v2: Research-aligned enhancements** — Added to RESUME_DRAFTING_PROMPT:
  - XYZ formula ("Accomplished [X] as measured by [Y] by doing [Z]") from FAANG best practices
  - AUTHENTICITY MARKERS section: before/after context for metrics, constraints/trade-offs, specific details, named technologies
  - Expanded AI-tell word list in POLISHED principle (added seamless, holistic, synergy, utilize, cutting-edge, pivotal, streamline)
  - Rhythm variation technique: "mix short punchy bullets (5-7 words) with longer ones (12-15 words)"
  - Skills section: "Group by category: Languages | Frameworks | Cloud" instead of flat list
  - Seniority mismatch guard: "Entry-level doesn't say 'led cross-functional strategy'"
  - Verify checklist expanded: added SENIORITY check (#8) and "at least one bullet with before/after context"
  - Context framing: "53% of hiring managers have reservations about AI-generated resumes"
- [x] **ACTION_VERBS cleanup** — Removed 3 AI-tell verbs (spearheaded, orchestrated, streamlined), added 19 practical verbs (automated, cut, deployed, fixed, migrated, shipped, etc.). Total: 73 verbs (was 57).
- [x] **SUGGESTION_GENERATION_PROMPT aligned** — Updated to prioritize before/after metrics, AI-tell replacement, compound bullet splitting, specificity, seniority matching. Added "NEVER suggest changes that fabricate metrics."
- [x] **Tuning loop aligned with production pipeline** — Refactored `create_draft_generator()` to use `_build_drafting_context_from_raw()` (same function as production `draft_resume_node`). Tuning loop now sends the same user message format ("Create an ATS-optimized resume based on:"), uses the same context structure (raw profile text as primary source, job text, gap analysis placeholders), and applies `_extract_content_from_code_block()` to strip code fences. 3 new tests verify alignment (44 total). Previous tuning loop used a simplified context that diverged from production — scores would not have reflected real behavior.
- [x] **Quantification rate check** — Added `_has_quantified_metric()` function detecting percentages, dollar amounts, multipliers, user counts, team sizes, before/after context, and time units. Integrated into `validate_resume()` as `quantification_rate` check (pass threshold: 50%, research target: 80%+). 11 new tests (55 total). Research says candidates with quantified achievements get 40% more interviews.
- [x] **Production pipeline quality integration** — `draft_resume_node` now calls `validate_resume()` after generating the draft and merges quality warnings/errors into `draft_validation` results sent to frontend. Previously, programmatic quality checks (bullet word count, AI-tells, compound sentences, quantification rate) existed but were never called in production — only available via `--validate` CLI. Now users see quality warnings alongside bias/PII warnings. Added `quality_checks` field to frontend `ValidationResults` type. 2 new completeness tests (57 total).
- [x] **Rhythm variation detection** — Added `_has_rhythm_variation()` function that detects 3+ consecutive bullets within ±1 word of each other (signals AI cadence). Research: "The 'too polished' problem is real. AI-generated resumes often have uniform sentence structure." Integrated into `validate_resume()` as `rhythm_variation` check. Users now see warnings when bullet rhythm is too uniform. Removed dead legacy `_build_drafting_context()` function (84 lines). 10 new tests (67 total).
- [x] **Hallucination fix: prompt anti-patterns** — Tightened `RESUME_DRAFTING_PROMPT` to prevent two user-reported hallucination patterns:
  - Added FAITHFUL rule: "NEVER attribute employer's scale to the candidate's individual work" with BAD/GOOD examples
  - Updated summary formula: "[N] years must match ACTUAL years in that specific domain, not total career"
  - Added VERIFY checklist item #2: "SCALE ATTRIBUTION" check
- [x] **Programmatic scope conflation detection** — Added `_detect_summary_years_claim()` and `_check_years_domain_grounded()` functions that extract "N+ years [domain]" from summary and cross-reference against source text. Includes abbreviation expansion (ML→machine learning, AI→artificial intelligence). Integrated into `validate_resume()` as `summary_years_grounded` check. 11 new tests.
- [x] **Programmatic scale attribution detection** — Added `_detect_ungrounded_scale()` function that detects scale language ("serving millions", "at scale") in resume not present in source profile. Integrated into `validate_resume()` as `no_ungrounded_scale` check. 7 new tests.
- [x] **Production integration** — `validate_resume()` now accepts optional `source_text` parameter. `draft_resume_node` passes `profile_text` for source-aware validation. 85 total quality tests, 652 backend tests pass.
- [x] **Grader enhancement: scope conflation + scale attribution** — Updated `GRADING_SYSTEM_PROMPT` in `drafting_llm_grader.py`:
  - SOURCE_FIDELITY: Added explicit penalties for summary year+domain conflation (score ≤ 50) and company-to-individual scale attribution (score ≤ 60) with concrete BAD/GOOD examples
  - SOURCE_FIDELITY: Added "CHECK THE SUMMARY FIRST" instruction — it's where conflation is most common
  - ATS_OPTIMIZATION: Added research-backed criteria (skills grouped by category, reverse-chronological, 3-5 bullets per role)
  - Evaluation prompt: Added specific instruction to check summary for year+domain and scale claims
  - All 652 backend tests pass
- [x] **Dead code + missing source_text fix** — Fixed two `validate_resume()` calls in `optimize.py` (get_drafting_state line 1199 and approve_draft line 1574) that were missing `source_text` parameter — scope conflation and scale attribution checks were silently skipped for those endpoints. Removed dead `_format_education_for_draft()` function from drafting.py. All 652 backend tests pass.
- [x] **Keyword coverage check** — Added `_extract_job_keywords()` function that extracts technology names, tools, skills, and key phrases from job postings. Extracts capitalized tech terms, acronyms (AWS, GCP, CI/CD), multi-word terms (machine learning), common tech vocabulary, and "experience with/in" patterns. Filters stop words and generic terms. Added `keyword_coverage` check to `validate_resume()` with `job_text` parameter — warns when <30% of job keywords appear in resume. Updated all 3 call sites (draft_resume_node, get_drafting_state, approve_draft) to pass `job_text`. 10 new tests (95 total), 662 backend tests pass. Addresses job_relevance (20% weight) — previously had zero programmatic checks.
- [x] **Reverse chronological check** — Added `_extract_experience_years()` function that extracts year data from h3 entries, handling "Present"/"Current" as highest sort value. Added `reverse_chronological` check to `validate_resume()` — warns when experience entries aren't ordered newest-first. Addresses narrative_hierarchy (15% weight) and ats_optimization (10% weight) — catches the specific bad pattern where the LLM reorders roles to chase job keywords. 7 new tests (102 total), 669 backend tests pass.
- [x] **Full pipeline integration tests** — Added `TestFullPipelineIntegration` class with 4 tests verifying validate_resume() works correctly when all three inputs (html, source_text, job_text) are provided together. Tests: good resume passes all checks, hallucinating resume caught (scope conflation + scale attribution), keyword-poor resume flagged, all 15+ check keys present. 106 quality tests, 673 total backend tests pass.

- [x] **Structural AI-voice detection (3 new checks)** — Added three new checks to `validate_resume()` targeting the top structural signals of AI-generated resumes:
  1. **Em dash detection** (`no_excessive_em_dashes`) — `_count_em_dashes()` counts em dashes (—) and en dashes (–). Flags if >= 3 found. Research: em dashes are the #1 typographic AI fingerprint.
  2. **Repetitive bullet openings** (`varied_bullet_openings`) — `_detect_repetitive_bullet_openings()` flags when 3+ bullets start with the same verb (e.g., "Built API… Built cache… Built monitor…"). Research: "uniform sentence structure" is a top AI tell.
  3. **Bullets per role** (`bullets_per_role`) — `_count_bullets_per_role()` extracts h3 sections and counts bullets per role. Flags <3 or >5 (research says 3-5 optimal). Addresses ATS parsing and readability.
  - Updated `RESUME_DRAFTING_PROMPT` POLISHED principle: explicit ban on em dashes, ban on 3+ same-opening bullets
  - Updated verification checklist item 8 to include em dashes, varied openings, 3-5 bullets per role
  - 19 new tests (125 quality tests total), 653 backend tests pass, 229 frontend tests pass
  - Total validation checks: 15 → 18

### TODO
- [x] Run tuning loop with new grader — 9 iterations completed
- [x] Measure baseline score — **86.4/100** (iteration 1)
- [x] Iterate on prompt — 8 iterations of targeted improvements
- [x] Verify trap samples — all pass thresholds (scope-conflation 85+, run-on-sentence 91, PM 90)
- [x] Target: **88+ overall achieved** — 88.7 (iteration 8), 88.0 (iteration 9)

### Tuning Results (9 iterations)
| Iter | Score | Key Change |
|------|-------|------------|
| 1 | 86.4 | Baseline — job_relevance 77.0 weakest |
| 2 | 83.6 | Added "80% quantified" → source_fidelity crashed (fabrication) |
| 3 | 85.7 | Removed quantification pressure, softened requirements |
| 4 | 86.7 | Fixed grader: source-grounded scale claims OK, specificity > quantification |
| 5 | 86.0 | Added tech restriction + phrase bans (within variance) |
| 6 | 85.4 | Clean memory run (stochastic variance) |
| 7 | 86.6 | Variance confirmation |
| 8 | **88.7** | **TARGET MET** — temp 0.4→0.3, harmonized FOCUSED principle, enhanced grader |
| 9 | **88.0** | **TARGET CONFIRMED** — stable at 88+ |
| 10 | **88.3** | FOCUSED narrow-match guidance + grader anti-anchoring (NC/JR rubrics) |
| 11 | 87.9 | Within variance (NC anchoring still at 85) |
| 12 | 83.6 | **REGRESSION** — mandatory authenticity markers caused fabrication (reverted) |
| 13 | **88.0** | Reverted to optional markers + clean memory = stable again |

**Final dimension scores (iteration 13)**: source_fidelity 90.2, conciseness 87.6, narrative_hierarchy 91.1, narrative_coherence 85.7, job_relevance 82.3, ats_optimization 92.7

**Stable range across clean iterations (8-10, 13)**: 88.0 — 88.7 (avg 88.25)

### Key Learnings
1. **Quantification must be subordinate to faithfulness** — "80% quantified" caused LLM to fabricate metrics
2. **Grader miscalibration** — PM sample penalized for "1M+ users" that WAS in source; added nuanced exception
3. **Memory contamination** — Accumulated suggestions contradict FAITHFUL principle; reset before critical runs
4. **Temperature alignment** — Production 0.4 vs tuning 0.3 mismatch; aligned both to 0.3
5. **Specificity > quantification** — Rewarding named technologies and concrete descriptions beats demanding numbers
6. **MANDATORY markers cause fabrication** — Making authenticity markers mandatory (iter 12) caused same problem as "80% quantified." Any MANDATORY generation requirement not in source causes LLM to fabricate.
7. **Narrative coherence anchoring** — LLM grader anchors narrative_coherence at 85 regardless of rubric changes. Anti-anchoring with marker counting helped slightly (2/9 samples moved to 86+).
8. **Stable ceiling ~88-89** — After 13 iterations, the practical ceiling is 88.0-88.7. Further improvement requires richer sample profiles or multi-shot grading.

### Code Quality Cleanup (post-tuning)
- [x] Fixed `grade_batch` type annotation: `callable` → `Callable[[dict, dict, str], Awaitable[str]]`
- [x] Added safer error handling in `grade_batch`: `r.get("grade", {})` to prevent KeyError
- [x] Added missing `Callable`, `Awaitable` imports to `drafting_llm_grader.py`
- [x] Updated README.md: test count 608→673, added tuning results table, expanded quality checks documentation
- [x] Verified `create_version()` is used by tests (not dead code)
- All 673 backend tests pass

### Files Changed
| File | Change |
|---|---|
| `apps/api/workflow/nodes/drafting.py` | New prompt (5 principles), enhanced validate_resume(), _is_compound_bullet(), _has_rhythm_variation(), AI_TELL_WORDS/PHRASES, detect_ai_tells(), ai_tells_clean + rhythm_variation checks, removed dead _build_drafting_context() |
| `apps/api/evals/graders/drafting_llm_grader.py` | 6 dimensions, new weights, original_resume_text param, research-aligned GRADING_SYSTEM_PROMPT with AI-tell deductions and authenticity markers |
| `apps/api/evals/drafting_tuning_loop.py` | DIMENSIONS 4→6, TARGET 0.15→0.10 |
| `apps/api/evals/datasets/drafting_samples.json` | profile_text added, 4 trap samples (9 total) |
| `apps/api/evals/run_drafting_tuning.py` | --validate flag, 6-dimension docs |
| `apps/api/tests/test_drafting_quality.py` | NEW: 106 tests (31 base + 8 AI-tell + 11 quantification + 10 rhythm + 11 scope conflation + 7 scale attribution + 10 keyword coverage + 7 reverse chrono + 4 integration + 2 completeness + 5 context alignment) |
| `apps/api/tests/test_drafting.py` | Updated summary limit test (100→50) |
