## Step 1: BUILD RESEARCH STAGE

### Purpose
Build the Research stage of the resume optimization agent workflow.

### Ralph Loop Execution
```bash
/ralph-loop:ralph-loop "Read `specs/step1_research.md` and BUILD the research stage.

IMPORTANT:
- This is a BUILD spec—write code, do not execute the workflow
- Stack: React frontend, Python/FastAPI backend, LangGraph, Exa MCP
- After building each component, run relevant tests
- Fix any test failures before proceeding
- Commit working code after each major component

Process:
1. Read all success criteria below
2. Build code to satisfy each criterion
3. Write tests for each criterion (GIVEN/WHEN/THEN maps to test cases)
4. Run tests: python -m pytest tests/test_research*.py -v && npm run test -- Research
5. Fix failures and iterate
6. When ALL tests pass, output the completion signal

Output RESEARCH_STAGE_BUILT only when ALL success criteria pass." \
  --max-iterations 20 \
  --completion-promise "RESEARCH_STAGE_BUILT"
```

### Validation Commands
```bash
python -m pytest tests/test_research*.py -v
npm run test -- Research
npm run test -- useResearchStorage
npm run test -- ResearchProgress
npm run build
```


### Success Criteria (ALL must pass)

#### Input Handling
```
- [ ] GIVEN a LinkedIn URL and job listing URL
      WHEN user clicks "Start Research"
      THEN system creates a new session and begins research workflow

- [ ] GIVEN invalid LinkedIn URL format
      WHEN user clicks "Start Research"
      THEN system shows validation error and does not start

- [ ] GIVEN invalid job listing URL format
      WHEN user clicks "Start Research"
      THEN system shows validation error and does not start
```

#### LinkedIn Profile Fetch
```
- [ ] GIVEN a valid LinkedIn URL
      WHEN research workflow runs
      THEN system fetches profile via Exa MCP and extracts: name, headline, summary, experience[], education[], skills[]

- [ ] GIVEN Exa MCP returns error for LinkedIn fetch
      WHEN research workflow runs
      THEN system retries 3 times, then shows error with manual input fallback option
```

#### Job Listing Fetch
```
- [ ] GIVEN a valid job listing URL
      WHEN research workflow runs
      THEN system fetches and parses: title, company, requirements[], responsibilities[], nice_to_haves[]

- [ ] GIVEN job listing URL returns 404
      WHEN research workflow runs
      THEN system shows error "Job listing not found" with retry option
```

#### Company Research
```
- [ ] GIVEN a company name extracted from job listing
      WHEN research workflow runs
      THEN system fetches: recent_news[] (last 6 months), tech_stack[], culture_signals[], growth_stage

- [ ] GIVEN company research returns partial data
      WHEN research workflow runs
      THEN system continues with available data and marks missing fields as null
```

#### Similar Hires Research
```
- [ ] GIVEN company name and role title
      WHEN research workflow runs
      THEN system finds >= 2 profiles of people recently hired for similar roles

- [ ] GIVEN no similar hires found
      WHEN research workflow runs
      THEN system continues with empty array and logs warning
```

#### Ex-Employee Research
```
- [ ] GIVEN company name
      WHEN research workflow runs
      THEN system finds profiles of people who recently left and where they went

- [ ] GIVEN no ex-employee data found
      WHEN research workflow runs
      THEN system continues with empty array
```

#### Hiring Criteria Extraction
```
- [ ] GIVEN job listing content
      WHEN research workflow runs
      THEN system extracts: must_haves[], preferred[], keywords[], ats_keywords[]

- [ ] GIVEN job listing with vague requirements
      WHEN research workflow runs
      THEN system infers implicit criteria and marks confidence level
```

#### Ideal Profile Generation
```
- [ ] GIVEN all research data collected
      WHEN research workflow runs
      THEN system generates: experience_themes[], skill_priorities[], narrative_angles[]
```

#### Progress Tracking
```
- [ ] GIVEN research workflow running
      WHEN each sub-task starts
      THEN UI shows step as "in progress" with spinner

- [ ] GIVEN research workflow running
      WHEN each sub-task completes
      THEN UI shows step as "completed" with checkmark

- [ ] GIVEN research workflow running
      WHEN any sub-task completes
      THEN progress bar updates to reflect percentage complete

- [ ] GIVEN 7 research sub-tasks
      WHEN all complete
      THEN progress bar shows 100%
```

#### Persistence
```
- [ ] GIVEN research sub-task completes with data
      WHEN progress event received by frontend
      THEN data saves to localStorage immediately

- [ ] GIVEN user closes browser mid-research
      WHEN user returns and enters same LinkedIn + job URL
      THEN system prompts "Resume from step X?" or "Start fresh?"

- [ ] GIVEN user selects "Resume"
      WHEN research restarts
      THEN system skips completed steps and continues from last incomplete step

- [ ] GIVEN user selects "Start fresh"
      WHEN research restarts
      THEN system clears previous session and starts from beginning
```

#### Completion
```
- [ ] GIVEN all 7 research sub-tasks complete successfully
      WHEN workflow checks completion
      THEN system emits RESEARCH_COMPLETE and enables "Continue to Discovery" button

- [ ] GIVEN any required research data missing
      WHEN workflow checks completion
      THEN system does not emit RESEARCH_COMPLETE and shows which data is missing
```

### Completion Signal
```
Output <promise>RESEARCH_STAGE_BUILT</promise> when ALL criteria pass
```

### Max Iterations: 20

---
