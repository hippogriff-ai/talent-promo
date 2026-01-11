## Step 3: BUILD DRAFTING STAGE

### Purpose
Build the Drafting stage—collaborative resume editing with accept/decline/edit workflow.

### Validation Commands
```bash
python -m pytest tests/test_drafting*.py -v
npm run test -- Drafting
npm run test -- useDraftingStorage
npm run test -- useSuggestions
npm run test -- ResumeEditor
npm run test -- SuggestionCard
npm run test -- VersionHistory
npm run build
```

### Success Criteria (ALL must pass)

#### Stage Entry
```
- [ ] GIVEN discovery stage confirmed
      WHEN user clicks "Continue to Drafting"
      THEN system loads research + discovery data and generates initial resume draft

- [ ] GIVEN discovery stage not confirmed
      WHEN user tries to access Drafting
      THEN system redirects to Discovery with message
```

#### Initial Draft Generation
```
- [ ] GIVEN research data and discovered experiences
      WHEN drafting stage starts
      THEN system generates resume with: contact info, summary (2-4 sentences), experience[], skills[], education[]

- [ ] GIVEN initial draft generated
      WHEN displayed
      THEN draft saves to localStorage as v1.0
```

#### Suggestion Generation
```
- [ ] GIVEN initial draft and job listing
      WHEN draft displayed
      THEN system generates improvement suggestions

- [ ] GIVEN suggestion generated
      WHEN displayed
      THEN suggestion shows: location, original text, proposed text, rationale
```

#### Accept Action
```
- [ ] GIVEN suggestion displayed
      WHEN user clicks "Accept"
      THEN proposed change applies to resume immediately

- [ ] GIVEN user accepts suggestion
      WHEN change applied
      THEN new version saves to localStorage

- [ ] GIVEN user accepts suggestion
      WHEN saved
      THEN suggestion moves from pending to accepted list
```

#### Decline Action
```
- [ ] GIVEN suggestion displayed
      WHEN user clicks "Decline"
      THEN original text remains unchanged

- [ ] GIVEN user declines suggestion
      WHEN declined
      THEN new version saves to localStorage

- [ ] GIVEN user declines suggestion
      WHEN saved
      THEN suggestion moves from pending to declined list
```

#### User Edit Action
```
- [ ] GIVEN resume section displayed
      WHEN user clicks to edit directly
      THEN inline editor activates

- [ ] GIVEN user makes direct edit
      WHEN user saves edit
      THEN new version saves to localStorage

- [ ] GIVEN user makes direct edit
      WHEN saved
      THEN change_log records edit location and content
```

#### Version Control
```
- [ ] GIVEN any user action (accept/decline/edit)
      WHEN action completes
      THEN version number increments and saves to localStorage

- [ ] GIVEN > 5 versions exist
      WHEN new version saves
      THEN oldest version deletes automatically

- [ ] GIVEN user clicks "Version History"
      WHEN history displays
      THEN last 5 versions show with: version number, timestamp, action description

- [ ] GIVEN version history displayed
      WHEN user clicks "Restore" on previous version
      THEN resume content reverts to that version

- [ ] GIVEN version restored
      WHEN restored
      THEN new version creates as branch point (does not delete newer versions from history)
```

#### Auto-Checkpoint
```
- [ ] GIVEN user actively editing
      WHEN 5 minutes pass since last save
      THEN auto-checkpoint saves current state as new version
```

#### Manual Save
```
- [ ] GIVEN user clicks "Save Progress"
      WHEN clicked
      THEN current state saves as new version with trigger "manual_save"

- [ ] GIVEN save completes
      WHEN saved
      THEN UI shows "✓ Saved as vX.X"
```

#### Crash Recovery
```
- [ ] GIVEN drafting session exists in localStorage
      WHEN user returns to Drafting stage
      THEN system shows: "Resume from vX.X?" with last saved time and progress

- [ ] GIVEN recovery prompt displayed
      WHEN user clicks "Resume"
      THEN system loads state from localStorage and displays current draft + pending suggestions

- [ ] GIVEN recovery prompt displayed
      WHEN user clicks "Start Fresh"
      THEN system clears all drafting localStorage keys and regenerates from discovery data

- [ ] GIVEN recovery prompt displayed
      WHEN user clicks "Browse Versions"
      THEN version history displays with restore option for each
```

#### Resume Validation
```
- [ ] GIVEN resume draft
      WHEN validated
      THEN system checks: summary exists and <= 100 words

- [ ] GIVEN resume draft
      WHEN validated
      THEN system checks: >= 1 experience entry exists

- [ ] GIVEN resume draft
      WHEN validated
      THEN system checks: each experience bullet starts with action verb

- [ ] GIVEN resume draft
      WHEN validated
      THEN system checks: skills section exists with categories

- [ ] GIVEN resume draft
      WHEN validated
      THEN system checks: education section exists
```

#### Completion
```
- [ ] GIVEN all suggestions resolved (pending[] is empty)
      WHEN user clicks "Approve Draft"
      THEN system validates resume structure

- [ ] GIVEN validation passes
      WHEN approved
      THEN system sets draft_approved: true and enables "Continue to Export"

- [ ] GIVEN validation fails
      WHEN approved attempted
      THEN system shows validation errors and blocks approval

- [ ] GIVEN draft not approved
      WHEN user tries to access Export
      THEN system redirects to Drafting with message
```

### Completion Signal
```
Output <promise>DRAFTING_STAGE_BUILT</promise> when ALL criteria pass
```

### Max Iterations: 20

---
