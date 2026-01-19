# Memory Feature Spec

## Overview

A user memory system that captures editing preferences and feedback to personalize future resume drafts. The system learns silently from user behavior and allows explicit profile management.

## Goals

1. **Personalization**: Generate drafts that match the user's established style
2. **Cross-job learning**: Apply lessons from one application to future ones
3. **Transparency**: Let users view and edit what the system learned about them
4. **Continuous improvement**: Use feedback to improve draft quality over time

## User Stories

### As a returning user...
- I want my preferred writing style applied automatically to new drafts
- I want to see what the system learned about my preferences
- I want to correct any incorrect assumptions the system made
- I want to rate the quality of generated drafts

### As a new user...
- I want to start immediately without creating an account
- I want to optionally save my preferences for future sessions
- I want a simple magic link login (no passwords)

---

## Feature: User Preferences

### What We Capture

**Writing Style**
- Tone: formal, conversational, confident, humble
- Structure: bullet points vs paragraphs
- Action verbs: preferred verbs (e.g., "led" vs "managed" vs "spearheaded")
- Sentence length: concise vs detailed
- First person vs implied subject ("Led team" vs "I led the team")

**Content Choices**
- Section emphasis: which sections user expands vs trims
- Skills prioritization: which skills they highlight for different roles
- Experience framing: achievements vs responsibilities
- Quantification preference: heavy metrics vs qualitative descriptions

**Formatting**
- Section ordering preferences
- Layout density: compact vs spacious
- Header styling preferences

### How Preferences Are Learned

1. **Edit tracking**: Monitor what users change in the editor
   - Text additions/deletions
   - Section reordering
   - Style modifications

2. **Suggestion responses**: Track which AI suggestions are accepted vs rejected

3. **Pattern detection**: Identify consistent patterns across multiple sessions

### How Preferences Are Applied

- When generating a new draft, include user preferences in the prompt
- Rank AI suggestions based on alignment with user preferences
- Pre-populate settings based on learned preferences

---

## Feature: Explicit Ratings

### What Users Can Rate

**Per-Draft Ratings**
- Overall quality (1-5 stars)
- ATS optimization satisfaction (thumbs up/down)
- "Would send as-is" (yes/no)

**Per-Section Ratings** (optional)
- Flag sections that need more work
- Mark sections as "perfect"

### Rating UI

- Simple rating prompt after export
- Optional - user can skip
- Non-intrusive, appears as overlay after download

---

## Feature: User Profile

### Profile Contents

- Learned preferences (read-only or editable)
- Rating history summary
- Number of resumes created
- Last active date

### Profile UX

**Settings Page** (`/settings/profile`)
- Full view of all learned preferences
- Toggle individual preferences on/off
- Reset to defaults option
- Export/delete data option

**Editor Sidebar**
- Quick view of active preferences
- Toggle common preferences inline
- Link to full settings page

---

## Feature: Authentication

### Magic Link Flow

1. User enters email
2. System sends login link (valid 15 minutes)
3. User clicks link, authenticated
4. Session persists via secure cookie

### Anonymous Start

1. New users can use the app without auth
2. Preferences stored in localStorage
3. Prompt to save (create account) at key moments:
   - After first completed resume
   - When returning to the app
   - Before clearing browser data

### Data Migration

- When anonymous user creates account, localStorage preferences merge to server
- Conflict resolution: server data takes precedence if account exists

---

## V1 Scope (MVP)

### In Scope
- [ ] Preference capture from editing behavior
- [ ] Preference storage (localStorage + server with auth)
- [ ] Explicit draft ratings (post-export)
- [ ] User profile page (view/edit preferences)
- [ ] Editor sidebar (quick preference toggle)
- [ ] Magic link authentication
- [ ] Anonymous-to-authenticated migration

### Out of Scope (V2+)
- Outcome tracking (interviews, job offers)
- Implicit signals (time spent, revision patterns)
- Job-type specific preferences
- Preference sharing/templates
- A/B testing of preference impact

---

## Success Metrics

1. **Adoption**: % of users who create accounts to save preferences
2. **Engagement**: Returning user rate
3. **Satisfaction**: Average draft rating
4. **Efficiency**: Time to final draft (should decrease for returning users)

---

## Open Questions

1. How long should preferences persist without activity?
2. Should preferences be exportable/importable?
3. How do we handle preference drift over time?
4. What's the minimum data needed before auto-applying preferences?

---

## Dependencies

- User authentication system (magic link)
- Server-side storage for preferences
- Editor instrumentation for tracking edits
