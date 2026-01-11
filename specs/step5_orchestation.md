## Step 5: BUILD WORKFLOW ORCHESTRATION

### Purpose
Build the workflow orchestration connecting all 4 stages.

### Ralph Loop Execution
```bash
/ralph-loop "Read this spec and BUILD the workflow orchestration.

IMPORTANT:
- This is a BUILD spec—write code, do not execute the workflow
- After building each component, run relevant tests
- Fix any test failures before proceeding
- Commit working code after each major component

Process:
1. Read all success criteria below
2. Build code to satisfy each criterion
3. Write tests for each criterion
4. Run tests: python -m pytest tests/ -v && npm run test
5. Fix failures and iterate
6. When ALL tests pass, output the completion signal

Output WORKFLOW_BUILT only when ALL success criteria pass." \
  --max-iterations 15 \
  --completion-promise "WORKFLOW_BUILT"
```

### Success Criteria (ALL must pass)

#### Workflow Navigation
```
- [ ] GIVEN user on any stage
      WHEN viewing UI
      THEN stepper shows all 4 stages: Research → Discovery → Drafting → Export

- [ ] GIVEN current stage is Research
      WHEN stepper displayed
      THEN Research shows as active, others show as locked

- [ ] GIVEN stage complete
      WHEN stepper displayed
      THEN completed stage shows checkmark, next stage unlocks
```

#### Stage Transitions
```
- [ ] GIVEN Research complete
      WHEN RESEARCH_COMPLETE emitted
      THEN Discovery stage unlocks automatically

- [ ] GIVEN Discovery confirmed
      WHEN user clicks Continue
      THEN Drafting stage unlocks

- [ ] GIVEN Drafting approved
      WHEN user clicks Continue
      THEN Export stage unlocks

- [ ] GIVEN Export complete
      WHEN EXPORT_COMPLETE emitted
      THEN workflow shows "Complete" state with all downloads available
```

#### Stage Guards
```
- [ ] GIVEN user tries to access stage N
      WHEN stage N-1 not complete
      THEN system redirects to stage N-1 with message

- [ ] GIVEN user bookmarks Export URL directly
      WHEN user visits bookmark without completing prior stages
      THEN system redirects to earliest incomplete stage
```

#### Session Continuity
```
- [ ] GIVEN user completes Research and closes browser
      WHEN user returns
      THEN system detects session and prompts to continue from Discovery

- [ ] GIVEN user in middle of Discovery and closes browser
      WHEN user returns
      THEN system detects session and prompts to continue Discovery conversation

- [ ] GIVEN user in middle of Drafting and closes browser
      WHEN user returns
      THEN system detects session and shows version recovery prompt
```

#### New Session
```
- [ ] GIVEN user has completed workflow
      WHEN user clicks "Start New"
      THEN system prompts "Start fresh for new job application?"

- [ ] GIVEN user confirms new session
      WHEN confirmed
      THEN system clears all localStorage keys for previous session and starts Research

- [ ] GIVEN user has existing session
      WHEN user enters different LinkedIn + job URL
      THEN system creates new session (does not overwrite existing)
```

#### Error Recovery
```
- [ ] GIVEN any stage fails with error
      WHEN error occurs
      THEN system saves current state to localStorage before showing error

- [ ] GIVEN error displayed
      WHEN user clicks "Retry"
      THEN system resumes from last saved state

- [ ] GIVEN unrecoverable error
      WHEN displayed
      THEN system offers "Start Fresh" option while preserving completed stages
```

### Completion Signal
```
Output <promise>WORKFLOW_BUILT</promise> when ALL criteria pass
```

### Max Iterations: 15