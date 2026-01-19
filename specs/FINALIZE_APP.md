# Finalize App Spec

## Overview
This spec guides a coding agent through finalizing the Talent Promo resume optimization app. The goal is to clean up residual code, fix UI bugs, and stabilize the core workflow.

## Success Criteria
- All E2E tests pass (landing → research → discovery → drafting → export)
- No console errors in browser during workflow
- Frontend builds without TypeScript errors
- Backend tests pass (excluding removed features)
- App works fully anonymously (no login required)

---

## Phase 1: Auth Removal (Priority: HIGH)

### Goal
Remove magic link authentication system while keeping preferences/ratings working anonymously.

### Files to DELETE
```
# Backend - Auth Core
apps/api/routers/auth.py
apps/api/services/auth_service.py
apps/api/middleware/session_auth.py
apps/api/migrations/003_user_auth.sql
apps/api/tests/test_auth.py
apps/api/services/migration_service.py
apps/api/tests/test_migration.py
apps/api/tests/test_memory_flow.py

# Frontend - Auth Core
apps/web/app/hooks/useAuth.tsx
apps/web/app/components/auth/AuthGuard.tsx
apps/web/app/components/auth/SavePrompt.tsx
apps/web/app/auth/  (entire directory)
```

### Files to MODIFY

#### 1. `apps/api/main.py`
- Remove: `from routers import auth`
- Remove: `app.include_router(auth.router)`

#### 2. `apps/api/routers/preferences.py`
- Remove: imports from `middleware.session_auth` and `services.auth_service`
- Change: endpoints to work without user authentication
- Use: anonymous user ID from request header or generate one

#### 3. `apps/api/routers/ratings.py`
- Remove: imports from `middleware.session_auth` and `services.auth_service`
- Change: endpoints to work without user authentication
- Use: anonymous user ID from request header or generate one

#### 4. `apps/api/routers/optimize.py`
- Remove: any auth-related imports or checks
- Keep: rate limiting (IP-based)

#### 5. `apps/web/app/layout.tsx`
- Remove: `AuthProvider` import and wrapper
- Keep: other providers

#### 6. `apps/web/app/hooks/usePreferences.ts`
- Remove: `useAuth` import and dependency
- Change: always use localStorage (anonymous mode)

#### 7. `apps/web/app/components/optimize/RatingModal.tsx`
- Remove: `useAuth` import
- Change: always allow rating (no auth check)

#### 8. `apps/web/app/settings/profile/page.tsx`
- Remove: `useAuth` and `AuthGuard` imports
- Simplify: to preferences-only page (no user account info)

#### 9. `apps/web/app/page.tsx` (Landing page)
- Remove: any auth-related UI (login prompts, etc.)
- Keep: rate limit challenge UI

#### 10. Test files
- `apps/api/tests/test_preferences.py` - Remove auth mocking
- `apps/api/tests/test_ratings.py` - Remove auth mocking
- `apps/web/**/*.test.tsx` - Remove auth mocking where applicable

### Acceptance Criteria
- [ ] App loads without AuthProvider errors
- [ ] Preferences save to localStorage and persist
- [ ] Ratings submit without authentication
- [ ] No "useAuth must be used within AuthProvider" errors
- [ ] Frontend builds successfully
- [ ] Backend starts without auth router errors

---

## Phase 2: Anonymous User ID System (Priority: HIGH)

### Goal
Replace auth-based user identification with anonymous session IDs.

### Implementation

#### Backend: Add anonymous user header
```python
# In preferences.py, ratings.py
def get_anonymous_user_id(
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID")
) -> str:
    """Get anonymous user ID from header or generate one."""
    return x_anonymous_id or f"anon_{uuid.uuid4().hex[:12]}"
```

#### Frontend: Generate and persist anonymous ID
```typescript
// New utility: apps/web/app/utils/anonymousId.ts
const ANON_ID_KEY = "talent_promo:anonymous_id";

export function getAnonymousId(): string {
  let id = localStorage.getItem(ANON_ID_KEY);
  if (!id) {
    id = `anon_${crypto.randomUUID().slice(0, 12)}`;
    localStorage.setItem(ANON_ID_KEY, id);
  }
  return id;
}

// Use in API calls:
headers: { "X-Anonymous-ID": getAnonymousId() }
```

### Acceptance Criteria
- [ ] Anonymous ID generated on first visit
- [ ] Same ID persists across page reloads
- [ ] Preferences/ratings associated with anonymous ID
- [ ] No PII collected or stored

---

## Phase 3: E2E Test Verification (Priority: HIGH)

### Goal
Run full E2E test to discover and document UI bugs.

### Test Command
```bash
cd apps/web && npx playwright test e2e/tests/real-workflow-urls.spec.ts --headed
```

### Manual Test Checklist
Run through the app using chrome dev plugin or playwrite and verify:

#### Landing Page
- [ ] Form renders correctly
- [ ] LinkedIn URL and Job URL inputs work
- [ ] "Paste instead" toggle switches to textarea mode
- [ ] Human challenge question appears
- [ ] Answer input enables submit button
- [ ] Wrong answer shows error, right answer enables submit
- [ ] Rate limit message appears if exceeded (3/day per IP)
- [ ] Global limit message appears if exceeded (30/day total)
- [ ] Honeypot field is hidden (bot protection)
- [ ] Submit redirects to /optimize

#### Research Phase
- [ ] Progress indicators update in real-time
- [ ] "Live Progress" feed shows EXA fetches happening
- [ ] Profile card shows name, headline, experience count
- [ ] Job card shows title, company, tech stack
- [ ] **EXA Markdown Modal**:
  - [ ] "View/Edit Full Profile" button visible
  - [ ] Modal opens with full LinkedIn markdown (10K+ chars expected)
  - [ ] Headers (##) render as section titles
  - [ ] Bullet points render correctly
  - [ ] "Edit" button switches to textarea mode
  - [ ] User can add text and save
  - [ ] Character count shows in footer
- [ ] Gap Analysis section shows strengths and gaps
- [ ] "Continue to Discovery" button appears when research complete

#### Discovery Phase
- [ ] Questions appear one at a time
- [ ] No duplicate questions shown
- [ ] User can type and submit answers
- [ ] "Skip" button works
- [ ] Progress indicator shows question count
- [ ] Auto-advances to drafting when done

#### Drafting Phase
- [ ] Resume editor loads with content
- [ ] Toolbar buttons work (bold, italic, etc.)
- [ ] Undo/redo buttons work
- [ ] AI suggestions panel shows
- [ ] Accept/decline suggestions works
- [ ] Chat mode works for custom requests
- [ ] "Approve & Export" button works

#### Export Phase
- [ ] ATS score displays (clickable to expand report)
- [ ] ATS report shows matched/missing keywords
- [ ] Resume preview toggle shows optimized HTML
- [ ] Download buttons visible (PDF, DOCX, TXT, JSON)
- [ ] Downloads trigger file save
- [ ] Rating modal appears (optional, user-triggered)
- [ ] "Start New" button resets workflow

#### Session Recovery (Cross-session)
- [ ] Refresh page mid-workflow → "Resume Session" modal appears
- [ ] Click "Resume" → workflow continues from last step
- [ ] Click "Start Fresh" → resets to beginning
- [ ] Close browser, return later → session persists in localStorage
- [ ] Session data includes: threadId, current stage, profile/job data
- [ ] Error state shows "Retry" option

### Bug Documentation Format
```markdown
### BUG-XXX: [Short description]
- **Location**: [Component/file]
- **Steps to reproduce**: [1, 2, 3...]
- **Expected**: [What should happen]
- **Actual**: [What happens]
- **Priority**: P0/P1/P2
```

### Acceptance Criteria
- [ ] E2E test passes end-to-end
- [ ] All manual checklist items verified
- [ ] Any bugs found are documented

---

## Phase 4: Known Bug Fixes (Priority: MEDIUM)

### BUG-001: Discovery duplicate messages (ALREADY FIXED)
- **Status**: Fixed via `filteredMessages` in DiscoveryChat.tsx
- **Verify**: No duplicate questions appear in chat

### BUG-002: [To be discovered during E2E testing]

### BUG-003: [To be discovered during E2E testing]

---

## Phase 5: Code Cleanup (Priority: LOW)

### Goal
Remove dead code and unused imports.

### Tasks

#### 1. Remove unused imports
Run linter to find unused imports:
```bash
cd apps/api && ruff check . --select F401
cd apps/web && npm run lint
```

#### 2. Remove commented-out code
Search for large comment blocks that are dead code.

#### 3. Remove unused test fixtures
Check for test helpers that are no longer used.

#### 4. Clean up CONTINUITY.md
Remove references to removed features (auth, magic links).

### Acceptance Criteria
- [ ] No linter errors for unused imports
- [ ] No commented-out code blocks > 10 lines
- [ ] All tests still pass

---

## Phase 6: Discovery Prompt Tuning Loop (Priority: HIGH)

### Goal
Improve the Discovery agent's ability to ask thought-provoking questions that help users uncover hidden experiences attractive to hiring managers. Set up a mini eval loop where a coding agent can iteratively improve prompts until achieving 15% score improvement.

### Why This Matters
The Discovery phase is where we differentiate from generic resume builders. Great questions surface:
- Achievements the user forgot to mention
- Transferable skills they didn't recognize
- Impact metrics they never quantified
- Stories that resonate with hiring managers

### Silver Dataset: Test Samples

Create test samples at `apps/api/evals/datasets/discovery_samples.json`:

```json
{
  "samples": [
    {
      "id": "sample_001",
      "description": "Senior engineer applying to staff role - needs to surface leadership",
      "input": {
        "user_profile": {
          "name": "Alex Chen",
          "headline": "Senior Software Engineer",
          "experience": [
            {
              "company": "TechCorp",
              "position": "Senior Software Engineer",
              "achievements": ["Built microservices", "Mentored juniors"]
            }
          ],
          "skills": ["Python", "AWS", "Kubernetes"]
        },
        "job_posting": {
          "title": "Staff Engineer",
          "requirements": ["Technical leadership", "Cross-team collaboration", "System design"]
        },
        "gap_analysis": {
          "gaps": ["No explicit technical leadership examples", "Missing cross-team impact"],
          "strengths": ["Strong technical skills", "Mentoring experience"]
        }
      },
      "expected_question_qualities": [
        "Probes for specific leadership moments, not generic 'tell me about leadership'",
        "Asks about times they influenced decisions without formal authority",
        "Explores cross-team collaboration with concrete examples",
        "Challenges them to quantify mentoring impact"
      ],
      "gold_question_examples": [
        "When you mentored juniors, was there a time one of them surprised you by solving something you thought would take longer? What did you learn about your teaching approach?",
        "Think about a technical decision at TechCorp that affected teams beyond your own. How did you navigate getting buy-in from people who had different priorities?",
        "You built microservices - but I'm curious about a time the architecture you proposed was initially rejected. How did you handle that pushback?"
      ],
      "anti_patterns": [
        "Tell me about your leadership experience",
        "Describe a time you worked with other teams",
        "What are your greatest achievements?"
      ]
    },
    {
      "id": "sample_002",
      "description": "Product manager pivoting to engineering - needs to surface technical depth",
      "input": {
        "user_profile": {
          "name": "Jordan Smith",
          "headline": "Product Manager",
          "experience": [
            {
              "company": "StartupXYZ",
              "position": "Product Manager",
              "achievements": ["Launched mobile app", "Grew DAU 3x"]
            }
          ],
          "skills": ["SQL", "Python basics", "Data analysis"]
        },
        "job_posting": {
          "title": "Software Engineer",
          "requirements": ["Python", "API development", "Problem solving"]
        },
        "gap_analysis": {
          "gaps": ["No professional engineering experience", "Limited coding portfolio"],
          "strengths": ["Technical PM background", "Data skills", "Problem solving"]
        }
      },
      "expected_question_qualities": [
        "Surfaces hidden technical work PMs often do but don't highlight",
        "Explores automation scripts or tools they built",
        "Asks about debugging sessions with engineers",
        "Probes for side projects or learning initiatives"
      ],
      "gold_question_examples": [
        "As a PM, you probably had moments where you thought 'I could just write this myself' - did you ever actually do it? Even a quick script or automation?",
        "When engineers explained technical constraints to you, what made you understand vs. stay confused? Were there times you dug into the code yourself?",
        "Growing DAU 3x is impressive - I'm curious about the data analysis behind it. Did you write any SQL queries yourself, or build any dashboards from scratch?"
      ],
      "anti_patterns": [
        "Do you have any coding experience?",
        "What technical skills do you have?",
        "Why do you want to switch to engineering?"
      ]
    },
    {
      "id": "sample_003",
      "description": "Junior developer applying to mid-level - needs to surface impact beyond ticket completion",
      "input": {
        "user_profile": {
          "name": "Sam Rivera",
          "headline": "Software Developer",
          "experience": [
            {
              "company": "AgencyWeb",
              "position": "Junior Developer",
              "achievements": ["Completed sprint tickets", "Fixed bugs"]
            }
          ],
          "skills": ["React", "Node.js", "Git"]
        },
        "job_posting": {
          "title": "Mid-Level Frontend Engineer",
          "requirements": ["3+ years experience", "Performance optimization", "Code review"]
        },
        "gap_analysis": {
          "gaps": ["Experience level mismatch", "No performance optimization examples"],
          "strengths": ["Relevant tech stack", "Agency experience = variety"]
        }
      },
      "expected_question_qualities": [
        "Helps them see agency work as valuable variety, not 'just client work'",
        "Surfaces moments they went beyond ticket requirements",
        "Finds performance wins they may not have recognized",
        "Explores informal leadership or initiative"
      ],
      "gold_question_examples": [
        "In agency work, you probably touched many different codebases. Was there ever a client project where you thought 'this is built wrong' and you pushed to fix it properly instead of just shipping?",
        "Bug fixing can be tedious, but sometimes you find something that makes you go 'oh, this is why everything was slow'. Any moments like that where your fix had bigger impact than expected?",
        "When new developers joined, did anyone ever ask you how something worked? What did you find yourself explaining most often?"
      ],
      "anti_patterns": [
        "Describe your experience level",
        "What performance optimizations have you done?",
        "How many years of experience do you have?"
      ]
    }
  ]
}
```

### LLM-as-a-Judge Grader

Create grader at `apps/api/evals/graders/discovery_grader.py`:

```python
"""
Discovery Question Quality Grader

Evaluates discovery prompts on their ability to elicit hidden, valuable experiences
from users that will resonate with hiring managers.
"""

from typing import TypedDict
import json

class DiscoveryGradeResult(TypedDict):
    overall_score: float  # 0-100
    dimension_scores: dict[str, float]
    reasoning: str
    suggestions: list[str]

GRADING_PROMPT = """
You are evaluating AI-generated discovery questions for a resume optimization tool.

The goal of discovery questions is to help job seekers uncover experiences they forgot
to mention or didn't realize were valuable - the hidden gems that make hiring managers
say "tell me more about that!"

## Evaluation Dimensions (score each 0-100):

### 1. Thought-Provoking (25%)
- Does it make the user pause and think, not just recall?
- Does it challenge assumptions about what's "worth mentioning"?
- Would an executive coach ask this, or a checkbox form?

### 2. Specificity Seeker (25%)
- Does it push for concrete examples, not generalities?
- Does it ask about specific moments, decisions, or outcomes?
- Will the answer naturally include quantifiable details?

### 3. Gap Relevance (25%)
- Does it directly address the identified gaps?
- Will the answer help bridge the gap between profile and job requirements?
- Is it targeted to THIS job, not generic career advice?

### 4. Hidden Value Finder (25%)
- Does it surface experiences the user might overlook?
- Does it reframe "ordinary" work as valuable achievements?
- Will it help the user see themselves through a hiring manager's eyes?

## Anti-patterns (deduct points):
- Generic questions that could apply to anyone (-20)
- Questions that feel like a job interview, not coaching (-15)
- Yes/no questions that don't invite storytelling (-10)
- Questions about things already well-documented in profile (-10)

## Input:
User Profile: {user_profile}
Job Posting: {job_posting}
Gap Analysis: {gap_analysis}

Generated Questions: {generated_questions}

Gold Standard Examples (for reference): {gold_examples}
Anti-Pattern Examples (avoid these): {anti_patterns}

## Output JSON:
{{
  "overall_score": <0-100>,
  "dimension_scores": {{
    "thought_provoking": <0-100>,
    "specificity_seeker": <0-100>,
    "gap_relevance": <0-100>,
    "hidden_value_finder": <0-100>
  }},
  "reasoning": "<2-3 sentences explaining the score>",
  "best_question": "<which generated question was best and why>",
  "worst_question": "<which generated question was worst and why>",
  "suggestions": [
    "<specific suggestion to improve question quality>",
    "<another specific suggestion>"
  ]
}
"""

class DiscoveryGrader:
    def __init__(self, client):
        self.client = client

    async def grade(
        self,
        sample: dict,
        generated_questions: list[str]
    ) -> DiscoveryGradeResult:
        """Grade generated discovery questions against a sample."""

        prompt = GRADING_PROMPT.format(
            user_profile=json.dumps(sample["input"]["user_profile"], indent=2),
            job_posting=json.dumps(sample["input"]["job_posting"], indent=2),
            gap_analysis=json.dumps(sample["input"]["gap_analysis"], indent=2),
            generated_questions=json.dumps(generated_questions, indent=2),
            gold_examples=json.dumps(sample["gold_question_examples"], indent=2),
            anti_patterns=json.dumps(sample["anti_patterns"], indent=2),
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse JSON from response
        result = json.loads(response.content[0].text)
        return result

    async def grade_batch(
        self,
        samples: list[dict],
        question_generator: callable
    ) -> dict:
        """Grade a batch of samples and return aggregate metrics."""

        results = []
        for sample in samples:
            questions = await question_generator(sample["input"])
            grade = await self.grade(sample, questions)
            results.append({
                "sample_id": sample["id"],
                "grade": grade
            })

        # Aggregate scores
        avg_score = sum(r["grade"]["overall_score"] for r in results) / len(results)

        return {
            "average_score": avg_score,
            "individual_results": results,
            "improvement_suggestions": self._aggregate_suggestions(results)
        }

    def _aggregate_suggestions(self, results: list) -> list[str]:
        """Find common suggestions across all samples."""
        all_suggestions = []
        for r in results:
            all_suggestions.extend(r["grade"]["suggestions"])
        # Return unique suggestions, most common first
        from collections import Counter
        return [s for s, _ in Counter(all_suggestions).most_common(5)]
```

### Prompt Tuning Loop Runner

Create runner at `apps/api/evals/discovery_tuning_loop.py`:

```python
"""
Discovery Prompt Tuning Loop

Iteratively improves discovery prompts until achieving target improvement.
Designed for coding agents to run in a loop.
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime

TARGET_IMPROVEMENT = 0.15  # 15% improvement required
MAX_ITERATIONS = 10

class DiscoveryTuningLoop:
    def __init__(self, grader, prompt_file_path: str):
        self.grader = grader
        self.prompt_file = Path(prompt_file_path)
        self.history = []
        self.baseline_score = None

    async def run_iteration(self, question_generator: callable) -> dict:
        """Run one iteration of the tuning loop."""

        # Load samples
        samples_path = Path(__file__).parent / "datasets" / "discovery_samples.json"
        with open(samples_path) as f:
            samples = json.load(f)["samples"]

        # Grade current prompt
        result = await self.grader.grade_batch(samples, question_generator)

        # Record history
        iteration = {
            "timestamp": datetime.now().isoformat(),
            "iteration": len(self.history) + 1,
            "score": result["average_score"],
            "suggestions": result["improvement_suggestions"],
            "individual_scores": [
                {"sample": r["sample_id"], "score": r["grade"]["overall_score"]}
                for r in result["individual_results"]
            ]
        }
        self.history.append(iteration)

        # Set baseline on first run
        if self.baseline_score is None:
            self.baseline_score = result["average_score"]

        # Calculate improvement
        improvement = (result["average_score"] - self.baseline_score) / self.baseline_score

        return {
            "current_score": result["average_score"],
            "baseline_score": self.baseline_score,
            "improvement": improvement,
            "target_met": improvement >= TARGET_IMPROVEMENT,
            "iterations": len(self.history),
            "suggestions": result["improvement_suggestions"],
            "detailed_results": result["individual_results"]
        }

    def get_loop_status(self) -> dict:
        """Get current loop status for coding agent."""
        if not self.history:
            return {"status": "NOT_STARTED", "message": "Run first iteration"}

        latest = self.history[-1]
        improvement = (latest["score"] - self.baseline_score) / self.baseline_score

        if improvement >= TARGET_IMPROVEMENT:
            return {
                "status": "TARGET_MET",
                "message": f"Achieved {improvement:.1%} improvement (target: {TARGET_IMPROVEMENT:.0%})",
                "final_score": latest["score"],
                "iterations_taken": len(self.history)
            }

        if len(self.history) >= MAX_ITERATIONS:
            return {
                "status": "MAX_ITERATIONS",
                "message": f"Reached {MAX_ITERATIONS} iterations. Best improvement: {improvement:.1%}",
                "best_score": max(h["score"] for h in self.history)
            }

        return {
            "status": "IN_PROGRESS",
            "current_score": latest["score"],
            "improvement_so_far": improvement,
            "target": TARGET_IMPROVEMENT,
            "remaining_gap": TARGET_IMPROVEMENT - improvement,
            "suggestions_for_next_iteration": latest["suggestions"],
            "message": f"Score: {latest['score']:.1f}/100 | Improvement: {improvement:.1%} | Target: {TARGET_IMPROVEMENT:.0%}"
        }

    def save_history(self, path: str = None):
        """Save tuning history for analysis."""
        path = path or f"discovery_tuning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(path, "w") as f:
            json.dump({
                "baseline_score": self.baseline_score,
                "final_score": self.history[-1]["score"] if self.history else None,
                "iterations": self.history
            }, f, indent=2)
```

### CLI for Coding Agent

Create CLI at `apps/api/evals/run_discovery_tuning.py`:

```python
"""
CLI for Discovery Prompt Tuning Loop

Usage:
  python -m evals.run_discovery_tuning --check     # Check current score
  python -m evals.run_discovery_tuning --iterate   # Run one iteration
  python -m evals.run_discovery_tuning --loop      # Run until target met
  python -m evals.run_discovery_tuning --status    # Show loop status
"""

import argparse
import asyncio
import json
from pathlib import Path

async def main():
    parser = argparse.ArgumentParser(description="Discovery Prompt Tuning")
    parser.add_argument("--check", action="store_true", help="Check current score")
    parser.add_argument("--iterate", action="store_true", help="Run one iteration")
    parser.add_argument("--loop", action="store_true", help="Run until target met")
    parser.add_argument("--status", action="store_true", help="Show loop status")
    parser.add_argument("--offline", action="store_true", help="Offline mode (no LLM calls)")
    args = parser.parse_args()

    # Implementation here...
    print("Discovery Prompt Tuning Loop")
    print("=" * 50)

    if args.status:
        # Load and display status
        pass
    elif args.check:
        # Run grading without saving
        pass
    elif args.iterate:
        # Run one iteration, save results
        pass
    elif args.loop:
        # Run until target met or max iterations
        pass

if __name__ == "__main__":
    asyncio.run(main())
```

### Integration with Discovery Node

The discovery prompts live in `apps/api/workflow/nodes/discovery.py`. The tuning loop should:

1. **Extract current prompt template** from `_generate_discovery_prompts()` function
2. **Test it** against the silver dataset
3. **Provide feedback** via LLM-as-a-judge
4. **Allow modification** of the prompt
5. **Re-test** until 15% improvement achieved

### Acceptance Criteria
- [ ] Silver dataset created with 3+ diverse samples
- [ ] Each sample has: input context, expected qualities, gold examples, anti-patterns
- [ ] LLM-as-a-judge grader scores questions on 4 dimensions
- [ ] Tuning loop tracks baseline and measures improvement
- [ ] CLI allows coding agent to run iterations
- [ ] Loop terminates when 15% improvement achieved or max iterations reached
- [ ] History saved for analysis

### Example Coding Agent Workflow

```markdown
## Agent Task: Improve Discovery Prompts

1. Run baseline check:
   ```bash
   python -m evals.run_discovery_tuning --check
   ```
   Output: "Baseline score: 62/100"

2. Review suggestions:
   - "Questions are too generic - add specific context about the gap"
   - "Missing follow-up depth - probe for concrete examples"

3. Modify prompt in `apps/api/workflow/nodes/discovery.py`:
   - Update `_generate_discovery_prompts()`
   - Add more context about specific gaps
   - Use executive coach framing

4. Run iteration:
   ```bash
   python -m evals.run_discovery_tuning --iterate
   ```
   Output: "Score: 68/100 | Improvement: 9.7% | Target: 15%"

5. Review new suggestions, modify prompt again

6. Repeat until:
   ```bash
   python -m evals.run_discovery_tuning --status
   ```
   Output: "TARGET_MET - Achieved 16.2% improvement in 4 iterations"
```

---

## Phase 7: A/B Arena (Keep for Local) (Priority: LOW)

### Goal
Keep arena functionality working locally without admin auth.

### Changes Required
1. `apps/api/middleware/admin_auth.py` - Make verify_admin a no-op for local dev
2. Keep all arena files intact
3. Document in README how to access arena locally

### Acceptance Criteria
- [ ] Arena endpoints accessible without auth token in dev mode
- [ ] Production deployments should set REQUIRE_ADMIN_AUTH=true

---

## Execution Order

The coding agent should execute in this order:

1. **Phase 1**: Delete auth files (quick wins, reduces complexity)
2. **Phase 2**: Add anonymous ID system (enables preferences/ratings)
3. **Phase 3**: Run E2E tests (discover remaining bugs)
4. **Phase 4**: Fix discovered bugs (based on priority)
5. **Phase 5**: Code cleanup (polish)
6. **Phase 6**: Discovery prompt tuning loop (quality improvement)
7. **Phase 7**: Arena local mode (optional)

### Loop Protocol
After each phase:
1. Run relevant tests
2. Check frontend builds: `cd apps/web && npm run build`
3. Check backend tests: `cd apps/api && python -m pytest tests/ -x -q`
4. Document any new issues found
5. Update this spec with progress

---

## Progress Tracker

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Auth Removal | NOT STARTED | |
| Phase 2: Anonymous ID | NOT STARTED | |
| Phase 3: E2E Testing | NOT STARTED | |
| Phase 4: Bug Fixes | NOT STARTED | |
| Phase 5: Code Cleanup | NOT STARTED | |
| Phase 6: Discovery Tuning | NOT STARTED | Target: 15% improvement |
| Phase 7: Arena Local | NOT STARTED | |

---

## Environment Requirements

```bash
# Backend
cd apps/api
source .venv/bin/activate
uvicorn main:app --reload --port 8000

# Frontend
cd apps/web
npm run dev  # port 3001

# E2E Tests
cd apps/web
npx playwright test
```

## Test Commands

```bash
# Backend unit tests
cd apps/api && python -m pytest tests/ -v

# Frontend unit tests
cd apps/web && npm test

# E2E tests (headless)
cd apps/web && npx playwright test

# E2E tests (headed, for debugging)
cd apps/web && npx playwright test --headed

# Specific E2E test
cd apps/web && npx playwright test e2e/tests/real-workflow-urls.spec.ts
```
