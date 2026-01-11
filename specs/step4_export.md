## Step 4: BUILD EXPORT STAGE

### Purpose
Build the Export stage—generate ATS-optimized outputs and LinkedIn suggestions.

### Ralph Loop Execution
```bash
/ralph-loop "Read this spec and BUILD the export stage.

IMPORTANT:
- This is a BUILD spec—write code, do not execute the workflow
- Stack: React frontend, Python/FastAPI backend, LangGraph
- Export depends on Drafting stage outputs from localStorage
- Must generate ATS-optimized PDF, TXT, JSON outputs
- After building each component, run relevant tests
- Fix any test failures before proceeding
- Commit working code after each major component

Process:
1. Read all success criteria below
2. Build code to satisfy each criterion
3. Write tests for each criterion (GIVEN/WHEN/THEN maps to test cases)
4. Run tests: python -m pytest tests/test_export*.py -v && npm run test -- Export
5. Fix failures and iterate
6. When ALL tests pass, output the completion signal

Output EXPORT_STAGE_BUILT only when ALL success criteria pass." \
  --max-iterations 15 \
  --completion-promise "EXPORT_STAGE_BUILT"
```

### Validation Commands
```bash
python -m pytest tests/test_export*.py -v
python -m pytest tests/test_pdf_generator*.py -v
python -m pytest tests/test_ats_analyzer*.py -v
npm run test -- Export
npm run test -- ExportResults
npm run test -- ATSReport
npm run test -- LinkedInSuggestions
npm run build
```

### Success Criteria (ALL must pass)

#### Stage Entry
```
- [ ] GIVEN drafting stage approved
      WHEN user clicks "Continue to Export"
      THEN system loads approved draft and begins export workflow

- [ ] GIVEN drafting stage not approved
      WHEN user tries to access Export
      THEN system redirects to Drafting with message
```

#### ATS Optimization
```
- [ ] GIVEN approved draft and job listing keywords
      WHEN export workflow runs
      THEN system optimizes keyword density without changing meaning

- [ ] GIVEN optimization complete
      WHEN processed
      THEN system ensures formatting is ATS-parseable (no tables, no columns, no headers that break parsing)
```

#### PDF Generation
```
- [ ] GIVEN optimized resume content
      WHEN export workflow runs
      THEN system generates PDF file

- [ ] GIVEN PDF generated
      WHEN validated
      THEN PDF file size > 10KB

- [ ] GIVEN PDF generated
      WHEN parsed by text extractor
      THEN all text content is extractable (not image-based)
```

#### Plain Text Generation
```
- [ ] GIVEN optimized resume content
      WHEN export workflow runs
      THEN system generates plain text file for copy-paste
```

#### JSON Export
```
- [ ] GIVEN optimized resume content
      WHEN export workflow runs
      THEN system generates structured JSON for portability
```

#### ATS Analysis Report
```
- [ ] GIVEN optimized resume and job listing
      WHEN export workflow runs
      THEN system generates ATS report with: keyword_match_score (0-100)

- [ ] GIVEN ATS report generated
      WHEN displayed
      THEN report shows: matched_keywords[], missing_keywords[]

- [ ] GIVEN ATS report generated
      WHEN displayed
      THEN report shows: formatting_issues[] (should be empty if optimized correctly)

- [ ] GIVEN keyword_match_score < 70%
      WHEN displayed
      THEN system shows warning with suggestions to improve
```

#### LinkedIn Suggestions
```
- [ ] GIVEN optimized resume content
      WHEN export workflow runs
      THEN system generates LinkedIn headline suggestion

- [ ] GIVEN optimized resume content
      WHEN export workflow runs
      THEN system generates LinkedIn summary suggestion

- [ ] GIVEN optimized resume content
      WHEN export workflow runs
      THEN system generates experience bullet suggestions mapped to LinkedIn sections
```

#### Progress Tracking
```
- [ ] GIVEN export workflow running
      WHEN each step starts
      THEN UI shows step as "in progress"

- [ ] GIVEN export workflow running
      WHEN each step completes
      THEN UI shows step as "completed"

- [ ] GIVEN export steps: optimizing, generating_pdf, generating_txt, analyzing_ats, generating_linkedin
      WHEN all complete
      THEN progress shows 100%
```

#### Download
```
- [ ] GIVEN export complete
      WHEN user clicks "Download PDF"
      THEN PDF file downloads to user's device

- [ ] GIVEN export complete
      WHEN user clicks "Download TXT"
      THEN plain text file downloads

- [ ] GIVEN export complete
      WHEN user clicks "Download JSON"
      THEN JSON file downloads

- [ ] GIVEN export complete
      WHEN user clicks "Copy to Clipboard"
      THEN plain text copies to clipboard with success message
```

#### Persistence
```
- [ ] GIVEN export complete
      WHEN results saved
      THEN ATS report and LinkedIn suggestions persist to localStorage

- [ ] GIVEN user returns to Export stage
      WHEN previous results exist
      THEN system displays cached results with "Re-export" option
```

#### Completion
```
- [ ] GIVEN all export artifacts generated
      WHEN workflow checks completion
      THEN system emits EXPORT_COMPLETE

- [ ] GIVEN ATS score >= 70%
      WHEN displayed
      THEN system shows success state

- [ ] GIVEN ATS score < 70%
      WHEN displayed
      THEN system shows warning but still allows completion
```

### Completion Signal
```
Output <promise>EXPORT_STAGE_BUILT</promise> when ALL criteria pass
```

### Max Iterations: 15

---
