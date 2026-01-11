## Step 2: BUILD DISCOVERY STAGE

### Purpose
Build the Discovery stage—guided conversation to surface hidden/forgotten experiences.

### Ralph Loop Execution
```bash
/ralph-loop "Read `specs/step2_discovery.md` and BUILD the discovery stage.

IMPORTANT:
- This is a BUILD spec—write code, do not execute the workflow
- Stack: React frontend, Python/FastAPI backend, LangGraph
- Discovery depends on Research stage outputs from localStorage
- After building each component, run relevant tests
- Fix any test failures before proceeding
- Commit working code after each major component

Process:
1. Read all success criteria below
2. Build code to satisfy each criterion
3. Write tests for each criterion (GIVEN/WHEN/THEN maps to test cases)
4. Run tests: python -m pytest tests/test_discovery*.py -v && npm run test -- Discovery
5. Fix failures and iterate
6. When ALL tests pass, output the completion signal

Output DISCOVERY_STAGE_BUILT only when ALL success criteria pass." \
  --max-iterations 20 \
  --completion-promise "DISCOVERY_STAGE_BUILT"
```

### Validation Commands
```bash
python -m pytest tests/test_discovery*.py -v
npm run test -- Discovery
npm run test -- useDiscoveryStorage
npm run test -- DiscoveryChat
npm run test -- GapAnalysis
npm run build
```

### Success Criteria (ALL must pass)

#### Stage Entry
```
- [ ] GIVEN research stage complete
      WHEN user clicks "Continue to Discovery"
      THEN system loads research results from localStorage and generates gap analysis

- [ ] GIVEN research stage incomplete
      WHEN user tries to access Discovery
      THEN system redirects to Research stage with message
```

#### Gap Analysis
```
- [ ] GIVEN candidate profile and ideal profile
      WHEN discovery stage starts
      THEN system displays: gaps[] (missing qualifications), strengths[] (matching qualifications), opportunities[] (potential angles to explore)

- [ ] GIVEN gap analysis generated
      WHEN displayed to user
      THEN each gap links to specific job requirement it relates to
```

#### Discovery Prompts
```
- [ ] GIVEN gap analysis
      WHEN discovery stage starts
      THEN system generates >= 5 discovery prompts (questions to surface hidden experience)

- [ ] GIVEN discovery prompts generated
      WHEN displayed to user
      THEN prompts are ordered by relevance to highest-priority gaps
```

#### Conversation Flow
```
- [ ] GIVEN discovery prompt displayed
      WHEN user types response and submits
      THEN system saves message to localStorage immediately

- [ ] GIVEN user response received
      WHEN agent processes response
      THEN agent either: asks follow-up question, OR moves to next prompt, OR identifies discovered experience

- [ ] GIVEN agent identifies relevant experience in user response
      WHEN processing response
      THEN system extracts experience and adds to discovered_experiences[]

- [ ] GIVEN discovered experience extracted
      WHEN saved
      THEN system maps it to specific job requirements it addresses
```

#### Chat Persistence
```
- [ ] GIVEN conversation in progress
      WHEN user closes browser
      THEN conversation_log persists in localStorage

- [ ] GIVEN user returns to Discovery stage
      WHEN session exists in localStorage
      THEN system prompts "Continue conversation?" or "Start fresh?"

- [ ] GIVEN user selects "Continue"
      WHEN discovery resumes
      THEN full conversation history displays and agent continues from last prompt

- [ ] GIVEN user selects "Start fresh"
      WHEN discovery restarts
      THEN system clears conversation and regenerates prompts
```

#### Discovered Experiences
```
- [ ] GIVEN >= 1 experience discovered
      WHEN displayed in UI
      THEN each experience shows: description, source quote from conversation, mapped requirements[]

- [ ] GIVEN no experiences discovered after all prompts
      WHEN user confirms completion
      THEN system allows proceeding with warning "No additional experiences found"
```

#### Completion
```
- [ ] GIVEN >= 3 conversation exchanges complete
      WHEN user clicks "Discovery Complete"
      THEN system prompts for confirmation

- [ ] GIVEN user confirms completion
      WHEN confirmed
      THEN system sets confirmed: true in localStorage and enables "Continue to Drafting"

- [ ] GIVEN user has not confirmed
      WHEN user tries to access Drafting
      THEN system redirects to Discovery with message
```

### Completion Signal
```
Output <promise>DISCOVERY_STAGE_BUILT</promise> when ALL criteria pass
```

### Max Iterations: 20

---
