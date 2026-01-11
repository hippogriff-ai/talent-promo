# Resume Agent Build Orchestrator

## Instructions for Claude

You are building a resume optimization agent workflow. Build each stage sequentially using subagents. Do not proceed to the next stage until the current stage passes all tests.

## Build Flow

### Stage 1: Build Research
```
Use Task tool to spawn subagent:
- prompt: "Read specs/step1_research.md and BUILD everything specified. Run tests after each component. Report back when ALL success criteria pass or if blocked."
- Wait for subagent completion
- Verify: `python -m pytest tests/test_research*.py -v` exits 0
- Verify: `npm run build` exits 0
- If failed: fix issues and re-run subagent
- If passed: proceed to Step 2
```

### Stage 2: Build Discovery
```
Use Task tool to spawn subagent:
- prompt: "Read specs/step2_discovery.md and BUILD everything specified. Run tests after each component. Report back when ALL success criteria pass or if blocked."
- Wait for subagent completion
- Verify: `python -m pytest tests/test_discovery*.py -v` exits 0
- Verify: `npm run build` exits 0
- If failed: fix issues and re-run subagent
- If passed: proceed to Stage 3
```

### Stage 3: Build Drafting
Read specs/step3_drafting.md and BUILD everything specified.

IMPORTANT:
- This is a BUILD spec—write code, not execute workflow
- Stack: React frontend, Python/FastAPI backend, LangGraph
- Drafting depends on Discovery outputs from localStorage
- Must implement version control: max 5 versions in localStorage
- Run tests after each component
- Fix failures before proceeding

Process:
1. Read all success criteria in the spec
2. Build code to satisfy each criterion
3. Write tests for each criterion
4. Run: python -m pytest tests/test_drafting*.py -v
5. Run: npm run test -- Drafting
6. Run: npm run build
7. Fix any failures and iterate

Output <promise>DRAFTING_STAGE_BUILT</promise> only when ALL tests pass." 

### Stage 4: Build Export
```
Use Task tool to spawn subagent:
- prompt: "Read specs/step4_export.md and BUILD everything specified. Run tests after each component. Report back when ALL success criteria pass or if blocked."
- Wait for subagent completion
- Verify: `python -m pytest tests/test_export*.py -v` exits 0
- Verify: `npm run build` exits 0
- If failed: fix issues and re-run subagent
- If passed: proceed to Stage 5
```

### Stage 5: Build Orchestration
```
Use Task tool to spawn subagent:
- prompt: "Read specs/step5_orchestration.md and BUILD everything specified. Run tests after each component. Report back when ALL success criteria pass or if blocked."
- Wait for subagent completion
- Verify: `python -m pytest tests/ -v` exits 0
- Verify: `npm run test` exits 0
- Verify: `npm run build` exits 0
- If failed: fix issues and re-run subagent
- If passed: workflow complete
```

## Completion Signal
Output <promise>ALL_STAGES_BUILT</promise> when all 5 stages pass.