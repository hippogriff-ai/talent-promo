# Talent Promo - Product Specification

**Version**: 2.0
**Last Updated**: 2025-01-12
**Status**: Draft for Review

---

## Executive Summary

**Talent Promo** is a B2C AI-powered resume optimization tool that helps individual job seekers maximize their ATS (Applicant Tracking System) scores for specific job postings.

### Core Promise
> "Paste your resume and job posting → Get an ATS-optimized resume in under 60 seconds"

### Business Model
- **Freemium SaaS**: 3 resumes/month free, paid tiers for more
- **Monetization**: Premium features (unlimited resumes, priority processing, history)

---

## Target User

### Primary Persona: Active Job Seeker
- **Who**: Individual professionals actively applying to jobs
- **Pain**: Generic resumes get filtered by ATS before human review
- **Need**: Tailored resume for each application, fast turnaround
- **Behavior**: Applies to 5-20 jobs/week, needs quick iteration

### User Journey
```
1. Find job posting → 2. Paste resume + job → 3. AI optimizes → 4. Download → 5. Apply
                              ↑                      ↓
                         [Under 60s]          [ATS Score 85%+]
```

---

## Core Value Proposition

### Quality Dimensions (All Required for "Good" Score)

| Dimension | Target | How We Measure |
|-----------|--------|----------------|
| **Keyword Match** | ≥80% of job keywords | Count matched vs total job keywords |
| **Formatting** | 100% ATS-parseable | No tables, images, headers in margins |
| **Quantification** | ≥60% of bullets have metrics | Count bullets with numbers/percentages |
| **Action Verbs** | 100% bullets start with verbs | NLP verb detection on first word |

### Speed Target
| Current | Target | Improvement |
|---------|--------|-------------|
| ~120s (2 min) | <60s | 2x faster |

---

## Feature Roadmap

### Phase 1: Speed Optimization (Current Pain Point)
**Goal**: Reduce workflow time from 120s to <60s

### Phase 2: Multi-Resume Management
**Goal**: Users can save/manage resumes per job application

### Phase 3: Freemium Infrastructure
**Goal**: Usage tracking, tier enforcement, payment integration

---

## Phase 1: Speed Optimization

### TDD Specification

#### Test Suite: `tests/test_speed_optimization.py`

```python
# ============================================================================
# SPEED TESTS - All must pass for Phase 1 complete
# ============================================================================

class TestWorkflowSpeed:
    """
    GIVEN: A valid resume and job posting
    WHEN: Full optimization workflow runs
    THEN: Total time < 60 seconds
    """

    @pytest.mark.timeout(60)
    def test_full_workflow_under_60_seconds(self):
        """
        PASS CRITERIA:
        - Start to downloadable PDF < 60s
        - Includes: ingest, research, discovery (auto), drafting, export
        """
        pass

    def test_research_phase_under_20_seconds(self):
        """
        PASS CRITERIA:
        - Profile parsing < 5s
        - Job parsing < 5s
        - Company research < 10s (parallel EXA calls)
        """
        pass

    def test_drafting_phase_under_15_seconds(self):
        """
        PASS CRITERIA:
        - Resume generation < 10s
        - Suggestions generation < 5s
        """
        pass

    def test_export_phase_under_10_seconds(self):
        """
        PASS CRITERIA:
        - ATS analysis < 5s
        - PDF generation < 3s
        - LinkedIn suggestions < 2s
        """
        pass


class TestAutoDiscovery:
    """
    To hit 60s, discovery must be optional/automatic.
    """

    def test_skip_discovery_mode(self):
        """
        GIVEN: User opts for "Quick Mode"
        WHEN: Workflow runs
        THEN: Discovery phase is skipped, uses resume as-is
        """
        pass

    def test_auto_discovery_extracts_from_resume(self):
        """
        GIVEN: No human-in-the-loop
        WHEN: Auto-discovery runs
        THEN: Experiences extracted from resume text automatically
        """
        pass


class TestParallelProcessing:
    """
    All independent operations must run in parallel.
    """

    def test_research_calls_parallel(self):
        """
        PASS CRITERIA:
        - Culture, tech stack, similar hires, news run concurrently
        - Total research time < max(individual calls) + 2s overhead
        """
        pass

    def test_export_generation_parallel(self):
        """
        PASS CRITERIA:
        - ATS, LinkedIn, file generation run concurrently
        """
        pass
```

#### Acceptance Criteria Checklist

- [ ] `test_full_workflow_under_60_seconds` passes
- [ ] `test_research_phase_under_20_seconds` passes
- [ ] `test_drafting_phase_under_15_seconds` passes
- [ ] `test_export_phase_under_10_seconds` passes
- [ ] `test_skip_discovery_mode` passes
- [ ] `test_auto_discovery_extracts_from_resume` passes
- [ ] `test_research_calls_parallel` passes
- [ ] `test_export_generation_parallel` passes

---

## Phase 2: Multi-Resume Management

### Data Model

```
User (future)
  └── Job Applications
        ├── Job Application 1 (Google SWE)
        │     ├── job_url: "google.com/jobs/123"
        │     ├── job_text: "Senior Software Engineer..."
        │     ├── created_at: "2025-01-12"
        │     ├── status: "applied" | "interviewing" | "rejected" | "offer"
        │     └── Resume Versions
        │           ├── v1.0 (initial)
        │           ├── v1.1 (after suggestions)
        │           └── v1.2 (manual edits)
        │
        └── Job Application 2 (Meta PM)
              └── ...
```

### TDD Specification

#### Test Suite: `tests/test_multi_resume.py`

```python
# ============================================================================
# MULTI-RESUME TESTS - All must pass for Phase 2 complete
# ============================================================================

class TestJobApplicationCRUD:
    """
    Users can create, read, update, delete job applications.
    """

    def test_create_job_application(self):
        """
        GIVEN: User with resume text
        WHEN: POST /api/applications with job_url
        THEN: New job application created with initial resume version
        """
        pass

    def test_list_job_applications(self):
        """
        GIVEN: User with 5 job applications
        WHEN: GET /api/applications
        THEN: Returns paginated list sorted by created_at desc
        """
        pass

    def test_get_job_application_with_versions(self):
        """
        GIVEN: Job application with 3 resume versions
        WHEN: GET /api/applications/{id}
        THEN: Returns application with all versions
        """
        pass

    def test_delete_job_application(self):
        """
        GIVEN: Job application exists
        WHEN: DELETE /api/applications/{id}
        THEN: Application and all versions deleted
        """
        pass


class TestResumeVersioning:
    """
    Each job application tracks resume versions.
    """

    def test_initial_version_created_on_optimization(self):
        """
        GIVEN: New job application
        WHEN: Optimization completes
        THEN: v1.0 created with optimized resume
        """
        pass

    def test_new_version_on_edit(self):
        """
        GIVEN: Application with v1.0
        WHEN: User saves edit
        THEN: v1.1 created, v1.0 preserved
        """
        pass

    def test_restore_previous_version(self):
        """
        GIVEN: Application with v1.0, v1.1, v1.2
        WHEN: User restores v1.0
        THEN: v1.3 created with v1.0 content
        """
        pass

    def test_max_versions_limit(self):
        """
        GIVEN: Application with 10 versions
        WHEN: 11th version created
        THEN: Oldest version (except v1.0) deleted
        """
        pass


class TestResumeComparison:
    """
    Users can compare resume versions.
    """

    def test_diff_between_versions(self):
        """
        GIVEN: Two resume versions
        WHEN: GET /api/applications/{id}/diff?v1=1.0&v2=1.2
        THEN: Returns line-by-line diff
        """
        pass

    def test_ats_score_comparison(self):
        """
        GIVEN: Two resume versions
        WHEN: Compare requested
        THEN: Shows ATS score change (+5%, -3%, etc.)
        """
        pass
```

#### Frontend Tests: `e2e/tests/multi-resume.spec.ts`

```typescript
test.describe('Multi-Resume Management', () => {
  test('user can view all job applications', async ({ page }) => {
    // GIVEN: User with 3 job applications
    // WHEN: Navigate to /dashboard
    // THEN: See list of 3 applications with job titles
  });

  test('user can switch between job applications', async ({ page }) => {
    // GIVEN: 2 job applications open
    // WHEN: Click on second application
    // THEN: Editor shows that application's resume
  });

  test('user can compare versions side-by-side', async ({ page }) => {
    // GIVEN: Application with 2 versions
    // WHEN: Click "Compare versions"
    // THEN: Side-by-side diff view shown
  });

  test('user can duplicate application for similar job', async ({ page }) => {
    // GIVEN: Existing optimized application
    // WHEN: Click "Duplicate for new job"
    // THEN: New application created with copied resume
  });
});
```

#### Acceptance Criteria Checklist

- [ ] `test_create_job_application` passes
- [ ] `test_list_job_applications` passes
- [ ] `test_get_job_application_with_versions` passes
- [ ] `test_delete_job_application` passes
- [ ] `test_initial_version_created_on_optimization` passes
- [ ] `test_new_version_on_edit` passes
- [ ] `test_restore_previous_version` passes
- [ ] `test_max_versions_limit` passes
- [ ] `test_diff_between_versions` passes
- [ ] `test_ats_score_comparison` passes
- [ ] E2E: user can view all job applications
- [ ] E2E: user can switch between job applications
- [ ] E2E: user can compare versions side-by-side
- [ ] E2E: user can duplicate application for similar job

---

## Phase 3: Freemium Infrastructure

### TDD Specification

#### Test Suite: `tests/test_freemium.py`

```python
# ============================================================================
# FREEMIUM TESTS - All must pass for Phase 3 complete
# ============================================================================

class TestUsageTracking:
    """
    Track resume optimizations per user per month.
    """

    def test_count_optimizations_this_month(self):
        """
        GIVEN: User with 2 optimizations in January
        WHEN: GET /api/usage
        THEN: Returns {used: 2, limit: 3, resets_at: "2025-02-01"}
        """
        pass

    def test_usage_resets_monthly(self):
        """
        GIVEN: User with 3 optimizations in January
        WHEN: February 1st arrives
        THEN: Usage count resets to 0
        """
        pass


class TestTierEnforcement:
    """
    Free tier limited to 3 resumes/month.
    """

    def test_free_tier_allows_3_optimizations(self):
        """
        GIVEN: Free user with 2 optimizations
        WHEN: Start 3rd optimization
        THEN: Allowed
        """
        pass

    def test_free_tier_blocks_4th_optimization(self):
        """
        GIVEN: Free user with 3 optimizations
        WHEN: Start 4th optimization
        THEN: Returns 402 Payment Required with upgrade prompt
        """
        pass

    def test_paid_tier_unlimited(self):
        """
        GIVEN: Paid user with 50 optimizations
        WHEN: Start 51st optimization
        THEN: Allowed
        """
        pass


class TestUpgradeFlow:
    """
    Seamless upgrade when hitting limit.
    """

    def test_upgrade_prompt_on_limit(self):
        """
        GIVEN: Free user at limit
        WHEN: Tries to optimize
        THEN: Shows upgrade modal with pricing
        """
        pass

    def test_upgrade_unlocks_immediately(self):
        """
        GIVEN: User just upgraded
        WHEN: Tries to optimize
        THEN: Allowed without refresh
        """
        pass
```

#### Acceptance Criteria Checklist

- [ ] `test_count_optimizations_this_month` passes
- [ ] `test_usage_resets_monthly` passes
- [ ] `test_free_tier_allows_3_optimizations` passes
- [ ] `test_free_tier_blocks_4th_optimization` passes
- [ ] `test_paid_tier_unlimited` passes
- [ ] `test_upgrade_prompt_on_limit` passes
- [ ] `test_upgrade_unlocks_immediately` passes

---

## Quality Gates

### Before Phase 1 Complete
```bash
# All existing tests must pass
pytest apps/api/tests/ -v  # 174+ tests
npm run test --prefix apps/web  # 158+ tests

# New speed tests must pass
pytest apps/api/tests/test_speed_optimization.py -v

# E2E workflow under 60s
npm run test:e2e:workflow --prefix apps/web
```

### Before Phase 2 Complete
```bash
# All Phase 1 tests still pass
# Plus:
pytest apps/api/tests/test_multi_resume.py -v
npm run test:e2e:multi-resume --prefix apps/web
```

### Before Phase 3 Complete
```bash
# All Phase 1 + 2 tests still pass
# Plus:
pytest apps/api/tests/test_freemium.py -v
npm run test:e2e:freemium --prefix apps/web
```

---

## Success Metrics

| Metric | Current | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|--------|---------|----------------|----------------|----------------|
| Workflow time | 120s | <60s | <60s | <60s |
| ATS score avg | Unknown | ≥80% | ≥85% | ≥85% |
| User retention | N/A | N/A | 40% return | 60% return |
| Conversion rate | N/A | N/A | N/A | 5% free→paid |

---

## Open Questions

1. **Authentication**: Do we need user accounts for Phase 1, or just Phase 2+?
2. **Storage**: Should resumes be stored in DB or just browser localStorage until Phase 2?
3. **Pricing**: What are the exact tier prices for Phase 3?

---

## Appendix: Existing Test Coverage

| Area | Tests | Status |
|------|-------|--------|
| Research workflow | 16 | ✅ Passing |
| Discovery | 27 | ✅ Passing |
| Drafting | 26 | ✅ Passing |
| Export | 34 | ✅ Passing |
| Orchestration | 19 | ✅ Passing |
| Integration | 57 | ✅ Passing |
| Thread cleanup | 19 | ✅ Passing |
| Frontend components | 158 | ✅ Passing |
| **Total** | **356+** | ✅ |
